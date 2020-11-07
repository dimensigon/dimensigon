import base64
import math
import os
import typing as t

import aiohttp
from flask import current_app

from dimensigon import defaults
from dimensigon.domain.entities import Server
from dimensigon.utils import asyncio
from dimensigon.utils.typos import Id
from dimensigon.web import errors
from dimensigon.web import network as ntwrk

if t.TYPE_CHECKING:
    pass


async def async_send_file(dest_server: Server, transfer_id: Id, file,
                          chunk_size: int = None, chunks: int = None, max_senders: int = None,
                          auth=None, retries: int = 3):
    async def send_chunk(server: Server, view: str, _chunk, _chunk_size, sem, _session):
        async with sem:
            json_msg = dict(chunk=_chunk)

            with open(file, 'rb') as fd:
                fd.seek(_chunk * _chunk_size)
                chunk_content = base64.b64encode(fd.read(_chunk_size)).decode('ascii')
            json_msg.update(content=chunk_content)

            return await ntwrk.async_post(server, view_or_url=view,
                                          view_data=dict(transfer_id=str(transfer_id)), json=json_msg, auth=auth,
                                          session=_session)

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
                                             auth=auth)
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
                                       auth=auth)
        if not resp.ok:
            current_app.logger.error(f"Transfer {transfer_id}: Unable to change state to TRANSFER_ERROR")
        raise errors.ChunkSendError(data)
