import base64
import math
import os
import typing as t
from datetime import datetime

import aiohttp
from flask import current_app
from flask_jwt_extended import get_jwt_identity

from dm import defaults
from dm.domain.entities import Orchestration, Server, Scope, OrchExecution
from dm.use_cases.deployment import create_cmd_from_orchestration2, RegisterStepExecution
from dm.use_cases.exceptions import ErrorLock
from dm.use_cases.lock import lock, unlock
from dm.utils import asyncio
from dm.utils.typos import Kwargs, Id
from dm.web import db, executor
from dm.web.network import async_post, async_patch


async def async_send_file(dest_server: Server, transfer_id: Id, file,
                          chunk_size: int = None, chunks: int = None, max_senders: int = None,
                          auth=None, retries: int=1):
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
                if resp[1] != 201:
                    retry_chunks.append(chunk)
                elif resp[1] == 410:
                    current_app.logger.error(f"Transfer {transfer_id} is no longer available: {resp[0]}")
                    return

            if len(retry_chunks) == 0 and chunks != 1:
                data, code = await async_patch(dest_server, 'api_1_0.transferresource',
                                               view_data={'transfer_id': transfer_id},
                                               session=session,
                                               auth=auth)
                if code != 201:
                    current_app.logger.error(
                        f"Transfer {transfer_id}: Unable to create file at destination {dest_server.name}: "
                        f"{code}, {data}")
            l_chunks = retry_chunks
            retries -= 1
    if l_chunks:
        data = {c: responses[c].result() for c in l_chunks}
        current_app.logger.error(f"Error while trying to send chunks to server: {data}")
        return data


def deploy_orchestration(orchestration: t.Union[Id, Orchestration],
                         hosts: t.Dict[str, t.Union[t.List[Id]]],
                         params: Kwargs = None,
                         execution=None,
                         **kwargs):
    try:
        if not isinstance(orchestration, Orchestration):
            orchestration = Orchestration.query.get(orchestration)
        if not isinstance(execution, OrchExecution):
            exe = None
            if execution is not None:
                exe = OrchExecution.query.get(execution)
            if exe is None:
                exe = OrchExecution(id=execution, orchestration=orchestration, target=hosts, params=params,
                                    executor_id=get_jwt_identity())
                db.session.add(exe)
                db.session.commit()
        current_app.logger.debug(
            f"Execution {exe.id}: Launching orchestration {orchestration} on {hosts} with {params}")
        return _deploy_orchestration(orchestration, params, hosts, exe, **kwargs)
    except Exception as e:
        current_app.logger.exception(f"Execution {exe.id}: Error while executing orchestration {orchestration}")
        raise


def _deploy_orchestration(orchestration: Orchestration, params: Kwargs, hosts: t.Dict[str, t.List[Id]],
                          execution: OrchExecution,
                          auth=None, max_parallel_tasks=None
                          ):
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
    cc = create_cmd_from_orchestration2(orchestration, params, hosts=hosts, executor=executor, auth=auth,
                                        register=rse)
    servers = Server.query.filter(Server.id.in_(hosts['all'])).all()
    try:
        applicant = lock(Scope.ORCHESTRATION, servers)
    except ErrorLock as e:
        execution.end_time = datetime.now()
        execution.success = False
        execution.message = str(e)
        db.session.commit()
        return {'error': f'{e}'}
    try:
        execution.success = cc.invoke()
        if not execution.success and orchestration.undo_on_error:
            execution.undo_success = cc.undo()
        execution.end_time = datetime.now()
        db.session.commit()
    finally:
        unlock(Scope.ORCHESTRATION, applicant=applicant, servers=servers)
    return cc.result
