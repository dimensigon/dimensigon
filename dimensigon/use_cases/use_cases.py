# business functions related with business logic
import base64
import logging
import math
import os
import subprocess
import typing as t

import aiohttp
from flask import current_app

from dimensigon import defaults
from dimensigon.domain.entities import Server
from dimensigon.utils import asyncio
from dimensigon.utils.typos import Id
from dimensigon.web import network as ntwrk, errors
from dimensigon.web.network import get

catalog_logger = logging.getLogger('dm.catalog')


def run_elevator(file, new_version, logger):
    logger.info(f"Upgrading to version {new_version}")
    stdout = open('elevator.out', 'a')
    cmd = ['python', 'elevator.py', 'upgrade', file, str(new_version)]
    logger.debug(f"Running command {' '.join(cmd)}")
    subprocess.Popen(cmd, stdin=None, stdout=stdout, stderr=stdout, close_fds=True, env=os.environ)
    stdout.close()


def get_software(server: Server, auth) -> t.Tuple[str, str]:
    resp, code = get(server, 'api_1_0.software_dimensigon', auth=auth)
    if code == 200:
        content = base64.b64decode(resp.get('content').encode('ascii'))

        file = os.path.join(current_app.config['SOFTWARE_REPO'], 'dimensigon', resp.get('filename'))
        with open(file, 'wb') as fh:
            fh.write(content)
        return file, resp.get('version')
    else:
        return None, None


async def async_send_file(dest_server: Server, transfer_id: Id, file,
                          chunk_size: int = None, chunks: int = None, max_senders: int = None,
                          identity=None, retries: int = 3):
    async def send_chunk(server: Server, view: str, _chunk, _chunk_size, sem, _session):
        async with sem:
            json_msg = dict(chunk=_chunk)

            with open(file, 'rb') as fd:
                fd.seek(_chunk * _chunk_size)
                chunk_content = base64.b64encode(fd.read(_chunk_size)).decode('ascii')
            json_msg.update(content=chunk_content)

            return await ntwrk.async_post(server, view_or_url=view,
                                          view_data=dict(transfer_id=str(transfer_id)), json=json_msg,
                                          session=_session, identity=identity)

    chunk_size = chunk_size or defaults.CHUNK_SIZE
    max_senders = max_senders or defaults.MAX_SENDERS
    chunks = chunks or math.ceil(os.path.getsize(file) / chunk_size)
    retries = retries
    sem = asyncio.Semaphore(max_senders)
    l_chunks = [c for c in range(0, chunks)]
    async with aiohttp.ClientSession() as session:
        while retries > 0:
            responses = {}
            retry_chunks = []
            for chunk in l_chunks:
                task = asyncio.create_task(
                    send_chunk(dest_server, 'api_1_0.transferresource', chunk, chunk_size, sem, session))
                responses.update({chunk: task})

            for chunk, task in responses.items():
                resp = await task
                if resp.code != 201:
                    retry_chunks.append(chunk)
                elif resp.code == 410:
                    raise errors.TransferNotInValidState(transfer_id, resp.msg['error'].get(['status'], None))

            if len(retry_chunks) == 0 and chunks != 1:
                resp = await ntwrk.async_put(dest_server, 'api_1_0.transferresource',
                                             view_data={'transfer_id': transfer_id},
                                             session=session,
                                             identity=identity)
                if resp.code != 201:
                    current_app.logger.error(
                        f"Transfer {transfer_id}: Unable to create file at destination {dest_server.name}: "
                        f"{resp}")
            l_chunks = retry_chunks
            retries -= 1
    if l_chunks:
        data = {c: responses[c].result() for c in l_chunks}
        resp = await ntwrk.async_patch(dest_server, 'api_1_0.transferresource',
                                       view_data={'transfer_id': transfer_id},
                                       json={'status': 'TRANSFER_ERROR'},
                                       session=session,
                                       identity=identity)
        if not resp.ok:
            current_app.logger.error(f"Transfer {transfer_id}: Unable to change state to TRANSFER_ERROR")
        raise errors.ChunkSendError(data)