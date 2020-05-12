import base64
import typing as t
from datetime import datetime

import aiohttp
from flask import current_app
from flask_jwt_extended import get_jwt_identity

from dm.domain.entities import Orchestration, Server, Scope, OrchExecution
from dm.use_cases.deployment import create_cmd_from_orchestration2, RegisterStepExecution
from dm.use_cases.exceptions import ErrorLock
from dm.use_cases.lock import lock, unlock
from dm.utils import asyncio
from dm.utils.typos import Kwargs, Id
from dm.web import db, executor
from dm.web.network import async_post, async_patch


async def async_send_file(dest_server: Server, transfer_id: Id, file, chunks: int, chunk_size: int,
                          max_senders: int, auth=None):
    async def send_chunk(server: Server, view: str, chunk):
        json_msg = {}
        json_msg.update(transfer_id=transfer_id)
        json_msg.update(chunk=chunk)

        with open(file, 'rb') as fd:
            fd.seek(chunk * chunk_size)
            chunk_content = base64.b64encode(fd.read(chunk_size)).decode('ascii')
        json_msg.update(content=chunk_content)

        return await async_post(server, view_or_url=view,
                                view_data=dict(transfer_id=str(transfer_id)), json=json_msg, auth=auth,
                                session=session)

    sem = asyncio.Semaphore(max_senders)
    responses = {}
    async with aiohttp.ClientSession() as session:
        async with sem:
            for chunk in range(0, chunks):
                task = asyncio.create_task(send_chunk(dest_server, 'api_1_0.transfer', chunk))
                responses.update({chunk: task})

        retry_chunks = []
        for chunk, task in responses.items():
            resp = await task
            if resp[1] != 201:
                retry_chunks.append(chunk)

        if len(retry_chunks) == 0:
            data, code = await async_patch(dest_server, 'api_1_0.transfer', view_data={'transfer_id': transfer_id},
                                           session=session,
                                           auth=auth)
            if code != 204:
                current_app.logger.error(
                    f"Transfer {transfer_id}: Unable to create file at destination {dest_server.name}: "
                    f"{code}, {data}")
        else:
            responses = {}
            async with sem:
                for chunk in retry_chunks:
                    task = asyncio.create_task(
                        send_chunk(dest_server, 'api_1_0.transfer', chunk))
                    responses.update({chunk: task})

            error_chunks = []
            for chunk, task in responses.items():
                resp = await task
                if resp[1] != 201:
                    error_chunks.append(chunk)
            if error_chunks:
                chunks, resp = list(zip(*[(chunk, r) for chunk, r in responses.items() if r[1] != 201]))
                errors = '\n'.join([str(r) for r in resp])
                current_app.logger.error(f"Error while trying to send chunks {', '.join(chunks)} to server")
            else:
                data, code = await async_patch(dest_server, 'api_1_0.transfer',
                                               view_data={'transfer_id': transfer_id},
                                               session=session,
                                               auth=auth)
                if code != 204:
                    current_app.logger.error(
                        f"Transfer {transfer_id}: Unable to create file at destination {dest_server.name}: "
                        f"{code}, {data}")


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
