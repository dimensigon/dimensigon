import base64
import json

import aiohttp
from flask import current_app
from flask_jwt_extended import create_access_token, get_jwt_identity

import dm.use_cases.exceptions as ue
from dm import defaults
from dm.domain.entities import *
from dm.domain.entities import bypass_datamark_update
from dm.domain.entities.locker import Scope
from dm.use_cases.lock import lock_scope
from dm.utils import asyncio
from dm.utils.helpers import get_distributed_entities
from dm.utils.typos import Id
from dm.web import db
from dm.web.network import get, async_post, async_patch


def upgrade_catalog(catalog, check_mismatch=True):
    de = get_distributed_entities()
    inside = set([name for name, cls in de])
    current_app.logger.debug(f'Actual entities: {inside}')

    outside = set(catalog.keys())
    current_app.logger.debug(f'Remote entities: {outside}')

    if check_mismatch and len(inside ^ outside) > 0:
        raise ue.CatalogMismatch(inside ^ outside)

    with bypass_datamark_update():
        for name, cls in de:
            if name in catalog:
                if len(catalog[name]) > 0:
                    current_app.logger.debug(
                        f"Adding/Modifying new '{name}' entities: \n{json.dumps(catalog[name], indent=2, sort_keys=True)}")
                for dto in catalog[name]:
                    o = cls.from_json(dto)
                    db.session.add(o)

        db.session.commit()


def upgrade_catalog_from_server(server):
    with lock_scope(Scope.UPGRADE, [server, Server.get_current()]):
        catalog_ver = db.session.query(db.func.max(Catalog.last_modified_at)).scalar()
        if catalog_ver:
            resp = get(server, 'api_1_0.catalog',
                       view_data=dict(data_mark=catalog_ver.strftime(defaults.DATEMARK_FORMAT)),
                       headers={'Authorization': 'Bearer ' + create_access_token(get_jwt_identity())})

            if 199 < resp[1] < 300:
                delta_catalog = resp[0]
                upgrade_catalog(delta_catalog)
            else:
                current_app.logger.error(f"Unable to get a valid response from server {server}: {resp[1]}, {resp[0]}")


async def send_software(dest_server: Server, transfer_id: Id, file, chunks: int, chunk_size: int,
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
                        send_chunk(dest_server, 'api_1_0.transfer'))
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
