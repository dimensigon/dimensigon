import base64
import math
import os
import typing as t

import aiohttp
from flask import current_app, g

import dimensigon.use_cases.lock as lock
from dimensigon import defaults
from dimensigon.domain.entities import Orchestration, Server, Scope, OrchExecution, User
from dimensigon.use_cases.deployment import create_cmd_from_orchestration, RegisterStepExecution
from dimensigon.utils import asyncio
from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import Id
from dimensigon.web import db, errors, executor
from dimensigon.web.network import async_post, async_put

if t.TYPE_CHECKING:
    from dimensigon.utils.var_context import VarContext


async def async_send_file(dest_server: Server, transfer_id: Id, file,
                          chunk_size: int = None, chunks: int = None, max_senders: int = None,
                          auth=None, retries: int = 1):
    async def send_chunk(server: Server, view: str, chunk, sem):
        async with sem:
            json_msg = dict(chunk=chunk)

            with open(file, 'rb') as fd:
                fd.seek(chunk * chunk_size)
                chunk_content = base64.b64encode(fd.read(chunk_size)).decode('ascii')
            json_msg.update(content=chunk_content)

            return await async_post(server, view_or_url=view,
                                    view_data=dict(transfer_id=str(transfer_id)), json=json_msg, auth=auth,
                                    session=session)

    chunk_size = chunk_size or defaults.CHUNK_SIZE
    max_senders = max_senders or defaults.MAX_SENDERS
    chunks = chunks or math.ceil(os.path.getsize(file) / chunk_size)
    retries = retries
    sem = asyncio.Semaphore(max_senders)
    responses = {}
    l_chunks = [c for c in range(0, chunks)]
    async with aiohttp.ClientSession() as session:
        while retries > 0:
            retry_chunks = []
            for chunk in l_chunks:
                task = asyncio.create_task(send_chunk(dest_server, 'api_1_0.transferresource', chunk, sem))
                responses.update({chunk: task})

            for chunk, task in responses.items():
                resp = await task
                if resp.code != 201:
                    retry_chunks.append(chunk)
                elif resp.code == 410:
                    raise errors.TransferNotInValidState(transfer_id, resp.msg['error'].get(['status'], None))

            if len(retry_chunks) == 0 and chunks != 1:
                resp = await async_put(dest_server, 'api_1_0.transferresource',
                                       view_data={'transfer_id': transfer_id},
                                       session=session,
                                       auth=auth)
                if resp.code != 201:
                    current_app.logger.error(
                        f"Transfer {transfer_id}: Unable to create file at destination {dest_server.name}: "
                        f"{resp}")
            l_chunks = retry_chunks
            retries -= 1
    if l_chunks:
        data = {c: responses[c].result() for c in l_chunks}
        raise errors.ChunkSendError(data)


def deploy_orchestration(orchestration: t.Union[Id, Orchestration],
                         hosts: t.Dict[str, t.Union[t.List[Id]]],
                         var_context: 'VarContext' = None,
                         execution: t.Union[Id, OrchExecution] = None,
                         executor: t.Union[Id, User] = None,
                         execution_server: t.Union[Id, Server] = None) -> OrchExecution:
    """deploy the orchestration

    Args:
        orchestration: id or orchestration to execute
        hosts: Mapping to all distributions
        params: VarContext configuration
        execution: id or execution to associate with the orchestration. If none, a new one is created
        executor: id or User who executes the orchestration
        execution_server: id or User who executes the orchestration

    Returns:
        dict: dict with tuple ids and the :class: CompletedProcess

    Raises:
        Exception: if anything goes wrong
    """
    execution = execution or var_context.globals.get('execution_id')
    executor = executor or var_context.globals.get('executor_id')
    hosts = hosts or var_context.globals.get('hosts')
    if not isinstance(orchestration, Orchestration):
        orchestration = Orchestration.query.get(orchestration)
    if not isinstance(execution, OrchExecution):

        if execution is not None:
            exe = OrchExecution.query.get(execution)
        else:
            exe = OrchExecution.query.get(var_context.globals.get('execution_id'))
        if exe is None:
            if not isinstance(executor, User):
                executor = User.query.get(executor)
            if executor is None:
                raise ValueError('executor must be set')
            if not isinstance(execution_server, Server):
                if execution_server is None:
                    try:
                        execution_server = g.server
                    except AttributeError:
                        execution_server = Server.get_current()
                    if execution_server is None:
                        raise ValueError('execution server not found')
                else:
                    execution_server = Server.query.get(execution_server)
            exe = OrchExecution(id=execution, orchestration_id=orchestration.id, target=hosts, params=dict(var_context),
                                executor_id=executor.id, server_id=execution_server.id)
            db.session.add(exe)
            db.session.commit()
    else:
        exe = execution
    current_app.logger.debug(
        f"Execution {exe.id}: Launching orchestration {orchestration} on {hosts} with {var_context}")
    return _deploy_orchestration(orchestration, var_context, hosts, exe)


def _deploy_orchestration(orchestration: Orchestration,
                          var_context: 'VarContext',
                          hosts: t.Dict[str, t.List[Id]],
                          execution: OrchExecution
                          ) -> OrchExecution:
    """
    Parameters
    ----------
    orchestration
        orchestration to deploy
    params
        parameters to pass to the steps

    Returns
    -------
    t.Tuple[bool, bool, t.Dict[int, dpl.CompletedProcess]]:
        tuple with 3 values. (boolean indicating if invoke process ended up successfully,
        boolean indicating if undo process ended up successfully,
        dict with all the executions). If undo process not executed, boolean set to None
    """
    rse = RegisterStepExecution(execution)
    execution.start_time = execution.start_time or get_now()
    cc = create_cmd_from_orchestration(orchestration, var_context, hosts=hosts, register=rse, executor=executor)

    # convert UUID into str as in_ filter does not handle UUID type
    all = [str(s) for s in hosts['all']]
    servers = Server.query.filter(Server.id.in_(all)).all()
    try:
        applicant = lock.lock(Scope.ORCHESTRATION, servers, execution.id)
    except errors.LockError as e:
        execution.end_time = get_now()
        execution.success = False
        execution.message = str(e)
        db.session.commit()
        raise
    try:
        execution.success = cc.invoke()
        if not execution.success and orchestration.undo_on_error:
            execution.undo_success = cc.undo()
        execution.end_time = get_now()
        db.session.commit()
    except Exception as e:
        current_app.logger.exception("Exception while executing invocation command")

    finally:
        lock.unlock(Scope.ORCHESTRATION, applicant=applicant, servers=servers)
    db.session.refresh(execution)
    return execution
