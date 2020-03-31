import datetime
import json
import logging
import os
import subprocess
import typing as t

import aiohttp
import requests
from bs4 import BeautifulSoup
from flask import current_app
from flask_jwt_extended import create_access_token
from pkg_resources import parse_version

from dm import __version__ as dm_version, defaults
from dm.domain.entities import Software, SoftwareServerAssociation, Server, Dimension, Transfer, \
    TransferStatus, Catalog, Scope
from dm.use_cases import exceptions as ue
from dm.use_cases.interactor import upgrade_catalog_from_server, update_table_routing_cost
from dm.use_cases.lock import lock_scope
from dm.utils import asyncio
from dm.utils.helpers import get_filename_from_cd, md5
from dm.web import db
from dm.web.network import async_get, HTTPBearerAuth, post, patch

logger = logging.getLogger('dm.background')


def process_check_new_versions(app=None, timeout_wait_transfer=None, refresh_interval=None):
    """
    checks if new version in repo

    Parameters
    ----------
    app:
        app to load the context
    timeout_wait_transfer:
        timeout waiting tranfer file to end.
    refresh_interval:
        time period to check if tranfer ended. Normally, used for test purposes

    Returns
    -------

    """
    ctx = None
    if app:
        ctx = app.app_context()
        ctx.push()
    try:
        current_server = Server.get_current()
        current_dimension = Dimension.get_current()
        logger.info('Starting Upgrade Process')
        base_url = os.environ.get('GIT_REPO') \
                   or current_app.config.get('GIT_REPO') \
                   or 'https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000'
        releases_uri = '/dimensigon/dimensigon/releases'
        try:
            r = requests.get(base_url + releases_uri, verify=current_app.config['SSL_VERIFY'], timeout=10)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            r = None
            logger.info('Unable to contact to main repo')

        # get new versions from repo
        if r and r.status_code == 200:
            # get current software
            software_list: t.List = Software.query.filter_by(name='dimensigon').all()
            software_list.sort(key=lambda s: parse_version(s.version))
            gogs_versions = {}

            html_content = r.text
            soup = BeautifulSoup(html_content, 'html.parser')
            for li in soup.find(id='release-list').find_all('li'):
                version = li.h4.a.get_text(strip=True)
                uris = [a.attrs['href'] for a in li.find('div', class_='download').find_all('a') if
                        a.attrs['href'].endswith('tar.gz')]
                if len(uris) > 0:
                    gogs_versions.update({parse_version(version): uris[0]})
            if len(software_list) > 0:
                max_version = parse_version(software_list[-1].version)
            else:
                max_version = parse_version('0')
            new_versions = [gogs_ver for gogs_ver in gogs_versions if gogs_ver > max_version]

            if new_versions:
                try:
                    with lock_scope(Scope.CATALOG):
                        logger.info(f"Downloading new versions {', '.join(map(str, new_versions))}")
                        with requests.Session() as s:
                            for new_version in new_versions:
                                r = s.get(base_url + gogs_versions[new_version],
                                          verify=current_app.config['SSL_VERIFY'])
                                filename = get_filename_from_cd(
                                    r.headers.get(
                                        'content-disposition')) or f"dimensigon-{gogs_versions[new_version].rsplit('/', 1)[-1]}"
                                file = os.path.join(current_app.config['SOFTWARE_REPO'], filename)
                                open(file, 'wb').write(r.content)

                                soft = Software(name='dimensigon', version=str(new_version), family='MIDDLEWARE',
                                                filename=filename, size=r.headers.get('content-length'),
                                                checksum=md5(file))
                                ssa = SoftwareServerAssociation(software=soft, server=current_server,
                                                                path=current_app.config['SOFTWARE_REPO'])
                                db.session.add(soft)
                                db.session.add(ssa)

                        db.session.commit()
                except ue.ErrorLock as e:
                    pass

        software_list: t.List = Software.query.filter_by(name='dimensigon').all()
        software_list.sort(key=lambda s: parse_version(s.version))

        if len(software_list) > 0 and parse_version(dm_version) < parse_version(software_list[-1].version):
            soft2deploy: Software = software_list[-1]
            # check if I should get software
            ssa = [ssa for ssa in soft2deploy.ssas if ssa.server == current_server]
            deployable = None
            if ssa:
                deployable = os.path.join(ssa[0].path, soft2deploy.filename)
            else:
                # get software if not in folder
                file = os.path.join(current_app.config['SOFTWARE_REPO'], soft2deploy.filename)
                if not os.path.exists(file):
                    ssa = min(soft2deploy.ssas,
                              key=lambda x: (x.server.route.cost or 999999) if x.server.route is not None else 999999)
                    logger.debug(f"Getting software from server {ssa.server}")
                    resp = post(ssa.server, 'api_1_0.software_send',
                                json={"software_id": str(soft2deploy.id),
                                      "dest_server_id": str(current_server.id),
                                      "dest_path": current_app.config[
                                          'SOFTWARE_REPO'],
                                      "chunk_size": 1024 * 1024 * 4,
                                      "max_senders": os.environ.get('WORKERS', 2)},
                                auth=HTTPBearerAuth(create_access_token('upgrader')))

                    if 199 < resp[1] < 300:
                        try:
                            trans_id = resp[0]['transfer_id']
                        except KeyError:
                            msg = f"transfer_id not found in data {resp[0]}"
                            logger.error(msg)
                            raise RuntimeError(msg)
                        logger.debug(f"Transfer ID {trans_id} generated")
                        trans: Transfer = Transfer.query.get(trans_id)
                        status = trans.wait_transfer(timeout=timeout_wait_transfer, refresh_interval=refresh_interval)
                        if status == TransferStatus.COMPLETED:
                            deployable = os.path.join(current_app.config['SOFTWARE_REPO'], soft2deploy.filename)
                        elif status in (TransferStatus.IN_PROGRESS, TransferStatus.WAITING_CHUNKS):
                            logger.debug(f"Timeout while waiting transfer ID {trans_id} to be completed")
                            raise ue.TransferTimeout()
                        else:
                            logger.debug(f"Error while waiting transfer ID {trans_id} to be completed")
                            raise ue.TransferError(status)
                    else:
                        logger.error(f'Unable to get file from server: {resp[0]}')
                        deployable = None
                else:
                    deployable = file
            if deployable:
                logger.info(f"Upgrading to version {soft2deploy.version}")
                stdout = open('elevator.out', 'a')
                cmd = ['python', 'elevator.py', 'upgrade', deployable, soft2deploy.version]
                logger.debug(f"Running command {' '.join(cmd)}")
                subprocess.Popen(cmd, stdin=None, stdout=stdout, stderr=stdout, close_fds=True, env=os.environ)
                stdout.close()
        else:
            logger.debug(f"No version to upgrade")
    finally:
        if ctx:
            ctx.pop()


async def _get_neighbour_catalog_data_mark():
    token = create_access_token('background')
    headers = {'Authorization': f"Bearer {token}"}
    server_responses = {}
    servers = Server.get_neighbours()
    logger.debug(f"Neighbour servers to check: {[s.name for s in servers]}")
    for server in servers:
        async with aiohttp.ClientSession(headers=headers,
                                         connector=aiohttp.TCPConnector(
                                             ssl=current_app.config['SSL_VERIFY'])) as session:
            server_responses[server] = await async_get(server, 'root.healthcheck', session=session)

        try:
            data = json.dumps(server_responses[server][0], indent=4, sort_keys=True)
        except json.decoder.JSONDecodeError:
            data = server_responses[server][0]
        except:
            data = f"Exception {server_responses[server][0].__class__.__name__}: {server_responses[server][0]}"
        code = server_responses[server][1]

        logger.debug(
            f"Response from server {server.name}: {code}, {data}")
    return server_responses


def check_catalog():
    logger.debug("Starting check catalog from neighbours")
    data = asyncio.run(_get_neighbour_catalog_data_mark())
    reference_server = None
    catalog_ver = db.session.query(db.func.max(Catalog.last_modified_at)).scalar()
    if catalog_ver:
        for server, response in data.items():
            if response[1] == 200 and 'catalog_version' in response[0]:
                new_catalog_ver = datetime.datetime.strptime(response[0]['catalog_version'],
                                                             defaults.DATEMARK_FORMAT)
                if new_catalog_ver > catalog_ver:
                    if response[0]['version'] == dm_version:
                        reference_server = server
                        catalog_ver = new_catalog_ver
                    else:
                        logger.debug(
                            f"Server {response[1]} has different software version {response[0]['version']}")
            else:
                msg = f"Error while trying to get healthcheck from server {server.name}. "
                if response[1]:
                    msg = msg + f"Response from server (code {response[1]}): {response[0]}"
                else:
                    msg = msg + f"Exception: {response[0]}"
                logger.warning(msg)
        if reference_server:
            logger.info(f"New catalog found from server {reference_server.name}: {catalog_ver}")
            upgrade_catalog_from_server(reference_server)
        else:
            logger.info(f"No server with higher catalog found")


def table_routing_process(discover_new_neighbours=False, check_current_neighbours=False):
    new_routes = update_table_routing_cost(discover_new_neighbours, check_current_neighbours)

    if len(new_routes) > 0:
        msg = {'server_id': str(Server.get_current().id),
               'route_list': [
                   r.to_json()
                   for r in new_routes
               ]}
        for s in Server.get_neighbours():
            try:
                r = patch(s, 'api_1_0.routes', json=msg, auth=HTTPBearerAuth(create_access_token('root')))
                if r[1] != 204:
                    logger.error(f"Unable to send new routing information to node {s}. {r[1]}, {r[0]}")
            except Exception as e:
                logger.error(
                    f"Exception raised while trying to send new routing information to node {s}. Exception: {e}")


def process_catalog_route_table(app=None):
    ctx = None
    if app:
        ctx = app.app_context()
        ctx.push()
        try:
            table_routing_process(discover_new_neighbours=True, check_current_neighbours=True)

            check_catalog()

        finally:
            if ctx:
                ctx.pop()
