import datetime
import json
import logging
import os
import subprocess
import typing as t
import uuid
from collections import namedtuple

import aiohttp
import requests
from bs4 import BeautifulSoup
from flask import current_app
from flask_jwt_extended import create_access_token
from pkg_resources import parse_version

from dm import __version__ as dm_version, defaults
from dm.domain.entities import Software, SoftwareServerAssociation, Server, Dimension, Transfer, \
    TransferStatus, Catalog, Scope, Route
from dm.network.low_level import check_host
from dm.use_cases import exceptions as ue
from dm.use_cases.interactor import upgrade_catalog_from_server
from dm.use_cases.lock import lock_scope
from dm.utils import asyncio
from dm.utils.helpers import get_filename_from_cd, md5, convert
from dm.web import db
from dm.web.network import async_get, HTTPBearerAuth, post, ping, get

logger = logging.getLogger('dm.background')
routing_logger = logging.getLogger('dm.background.routing')
catalog_logger = logging.getLogger('dm.background.catalog')
upgrader_logger = logging.getLogger('dm.background.upgrader')


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
        upgrader_logger.info('Starting Upgrade Process')
        base_url = os.environ.get('GIT_REPO') \
                   or current_app.config.get('GIT_REPO') \
                   or 'https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000'
        releases_uri = '/dimensigon/dimensigon/releases'
        try:
            r = requests.get(base_url + releases_uri, verify=current_app.config['SSL_VERIFY'], timeout=10)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            r = None
            upgrader_logger.info('Unable to contact to main repo')

        # get new versions from repo
        if r and r.status_code == 200:
            # get current software
            software_list: t.List = db.session.query(Software).filter_by(name='dimensigon').all()
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
                max_version = parse_version(dm_version)
            new_versions = [gogs_ver for gogs_ver in gogs_versions if gogs_ver > max_version]

            if new_versions:
                try:
                    with lock_scope(Scope.CATALOG):
                        upgrader_logger.info(f"Downloading new versions {', '.join(map(str, new_versions))}")
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
                    upgrader_logger.debug(f"Getting software from server {ssa.server}")
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
                            upgrader_logger.error(msg)
                            raise RuntimeError(msg)
                        upgrader_logger.debug(f"Transfer ID {trans_id} generated")
                        trans: Transfer = Transfer.query.get(trans_id)
                        status = trans.wait_transfer(timeout=timeout_wait_transfer, refresh_interval=refresh_interval)
                        if status == TransferStatus.COMPLETED:
                            deployable = os.path.join(current_app.config['SOFTWARE_REPO'], soft2deploy.filename)
                        elif status in (TransferStatus.IN_PROGRESS, TransferStatus.WAITING_CHUNKS):
                            upgrader_logger.debug(f"Timeout while waiting transfer ID {trans_id} to be completed")
                            raise ue.TransferTimeout()
                        else:
                            upgrader_logger.debug(f"Error while waiting transfer ID {trans_id} to be completed")
                            raise ue.TransferError(status)
                    else:
                        upgrader_logger.error(f'Unable to get file from server: {resp[0]}')
                        deployable = None
                else:
                    deployable = file
            if deployable:
                upgrader_logger.info(f"Upgrading to version {soft2deploy.version}")
                stdout = open('elevator.out', 'a')
                cmd = ['python', 'elevator.py', 'upgrade', deployable, soft2deploy.version]
                upgrader_logger.debug(f"Running command {' '.join(cmd)}")
                subprocess.Popen(cmd, stdin=None, stdout=stdout, stderr=stdout, close_fds=True, env=os.environ)
                stdout.close()
        else:
            upgrader_logger.debug(f"No version to upgrade")
    finally:
        if ctx:
            ctx.pop()


async def _get_neighbour_catalog_data_mark():
    token = create_access_token('background')
    headers = {'Authorization': f"Bearer {token}"}
    server_responses = {}
    servers = Server.get_neighbours()
    catalog_logger.debug(f"Neighbour servers to check: {[s.name for s in servers]}")
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

        catalog_logger.debug(
            f"Response from server {server.name}: {code}, {data}")
    return server_responses


def check_catalog():
    catalog_logger.debug("Starting check catalog from neighbours")
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
                        catalog_logger.debug(
                            f"Server {response[1]} has different software version {response[0]['version']}")
            else:
                msg = f"Error while trying to get healthcheck from server {server.name}. "
                if response[1]:
                    msg = msg + f"Response from server (code {response[1]}): {response[0]}"
                else:
                    msg = msg + f"Exception: {response[0]}"
                catalog_logger.warning(msg)
        if reference_server:
            catalog_logger.info(f"New catalog found from server {reference_server.name}: {catalog_ver}")
            upgrade_catalog_from_server(reference_server)
        else:
            catalog_logger.info(f"No server with higher catalog found")

TempRoute = namedtuple('TempRoute', ['proxy_server', 'gate', 'cost'])


def update_table_routing_cost(discover_new_neighbours=False, check_current_neighbours=False) -> t.Dict[
    Server, TempRoute]:
    """Gets route tables of all neighbours and updates its own table based on jump weights.
    Needs a Flask App Context to run.

    Parameters
    ----------
    discover_new_neighbours:
        tries to discover new neighbours
    check_current_neighbours:
        checks if current neighbours are still neighoburs

    Returns
    -------
    None
    """
    # get all neighbours
    temp_table_routes: t.Dict[uuid.UUID, t.List[TempRoute]] = {}
    changed_routes: t.Dict[Server, TempRoute] = {}
    me = Server.get_current()
    not_neighbours = Server.get_not_neighbours()
    routing_logger.debug('Updating routing table')
    not_neighbours_anymore = []
    if check_current_neighbours:
        neighbours = Server.get_neighbours()
        routing_logger.debug(
            f"Checking current neighbours: " + ', '.join([str(s) for s in neighbours]))
        for server in neighbours:
            route = server.route
            cost, time = ping(server, me, retries=2, timeout=10)
            if cost is None:
                default_gate = server.route.gate
                temp = [None, None, None]
                # try another gate
                for gate in server.gates:
                    # check not to connect with localhost gate from current node and not to check already checked gate
                    if gate != default_gate and ((gate.ip and not gate.ip.is_loopback) or (
                            gate.dns and gate.dns != 'localhost')):
                        if check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=2, delay=1, timeout=10):
                            temp[0] = None
                            temp[1] = gate
                            temp[2] = 0
                            break
                if temp[2] is None:
                    not_neighbours_anymore.append(server)
                if route.proxy_server != temp[0] or route.gate != temp[1] or route.cost != temp[2]:
                    changed_routes[server] = TempRoute(*temp)
                    route.proxy_server, route.gate, route.cost = temp

            # try:
            #     requests.get(server.url('root.healthcheck'), timeout=0.5,
            #                  verify=False)
            # except (requests.exceptions.ConnectTimeout, TimeoutError):
            #     # TODO: handle when a neighobur is not a neighbour anymore
            #     server.cost = None
            # else:
            #     server.cost = 0
            #     server.gateway = None
    if len(not_neighbours_anymore) > 0:
        routing_logger.debug(
            f"Lost direct connection to the following nodes: " + ', '.join([str(s) for s in not_neighbours_anymore]))

    if discover_new_neighbours:
        routing_logger.debug(
            f"Checking new neighbours: " + ', '.join([str(s) for s in not_neighbours_anymore]))
        for server in not_neighbours:
            for gate in server.gates:
                if (gate.ip and not gate.ip.is_loopback) or (gate.dns and gate.dns != 'localhost'):
                    if check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=2, delay=1, timeout=2):
                        routing_logger.debug(f'Node {server} is a new neighbour')
                        if server.route:
                            server.route.gate = gate
                            server.route.proxy_server = None
                            server.route.cost = 0
                            db.session.add(server.route)
                        else:
                            r = Route(destination=server, proxy_server=None, gate=gate, cost=0)
                            db.session.add(r)
                        changed_routes[server] = TempRoute(None, server.route.gate, server.route.cost)
                        break

    token = create_access_token(identity='root')
    pool_responses = []
    neighoburs = Server.get_neighbours()
    for server in neighoburs:
        pool_responses.append(get(server, 'api_1_0.routes', auth=HTTPBearerAuth(token)))

    for resp in pool_responses:
        if resp[1] == 200:
            msg = resp[0]

            likely_proxy_server_entity = db.session.query(Server).get(msg.get('server_id'))
            routing_logger.debug(
                f"route list got from server {likely_proxy_server_entity}: {json.dumps(msg['route_list'], indent=4)}")

            for route_json in msg['route_list']:
                route_json = convert(route_json)
                # noinspection PyTypeChecker
                route_json.destination_id = uuid.UUID(route_json.destination_id)
                if route_json.gate_id:
                    # noinspection PyTypeChecker
                    route_json.gate_id = uuid.UUID(route_json.gate_id)
                if route_json.proxy_server_id:
                    # noinspection PyTypeChecker
                    route_json.proxy_server_id = uuid.UUID(route_json.proxy_server_id)
                if route_json.destination_id != me.id \
                        and route_json.proxy_server_id != me.id \
                        and route_json.gate_id not in [g.id for g in me.gates]:
                    if route_json.destination_id not in temp_table_routes:
                        temp_table_routes.update({route_json.destination_id: []})
                    if route_json.cost is not None:
                        route_json.cost += 1
                        route_json.proxy_server_id = likely_proxy_server_entity.id
                        route_json.gate_id = None
                        temp_table_routes[route_json.destination_id].append(
                            TempRoute(likely_proxy_server_entity.id, None, route_json.cost))
                    elif route_json.cost is None:
                        # remove a routing if gateway cannot reach the destination
                        temp_table_routes[route_json.destination_id].append(
                            TempRoute(route_json.proxy_server_id, None, None))
        else:
            s = neighoburs[pool_responses.index(resp)]
            routing_logger.error(f"Error while connecting with {s}. Error: {resp[1]}, {resp[0]}")

    # Select new routes based on neighbour routes
    MAX_COST = 9999999
    neighbour_ids = [s.id for s in Server.get_neighbours()]
    for destination_id in filter(lambda s: s not in neighbour_ids, temp_table_routes.keys()):
        route = db.session.query(Route).filter_by(destination_id=destination_id).one_or_none()
        if not route:
            # TODO: handle how to create new server. If through repository or through new routes
            continue
        temp_table_routes[destination_id].sort(key=lambda x: x.cost or MAX_COST)
        if len(temp_table_routes[destination_id]) > 0:
            min_route = temp_table_routes[destination_id][0]
            proxy_server = db.session.query(Server).get(min_route.proxy_server)
            cost = min_route.cost
            if route.proxy_server != proxy_server or route.cost != cost:
                route.proxy_server = proxy_server
                route.gate = None
                route.cost = cost
                changed_routes[route.destination] = TempRoute(route.proxy_server,
                                                              route.gate,
                                                              route.cost)
                db.session.add(route)
                break

    data = {}
    for server, temp_route in changed_routes.items():
        data.update({str(server): {'proxy_server': str(temp_route.proxy_server), 'gate': str(temp_route.gate),
                                   'cost': str(temp_route.cost)}})
    routing_logger.debug(f'Changed routes from neighbours: {json.dumps(data, indent=4)}')
    return changed_routes

def table_routing_process(discover_new_neighbours=False, check_current_neighbours=False):
    new_routes = update_table_routing_cost(discover_new_neighbours, check_current_neighbours)

    if len(new_routes) > 0:
        # msg = {'server_id': str(Server.get_current().id),
        #        'route_list': [
        #            dict(destination_id=str(d.id),dm.l
        #                 proxy_server_id=str(getattr(r.proxy_server, 'id')) if getattr(r.proxy_server, 'id', None) else None,
        #                 gate_id=str(getattr(r.gate, 'id')) if getattr(r.gate, 'id', None) else None,
        #                 cost=r.cost)
        #            for d, r in new_routes.items()
        #        ]}
        # for s in Server.get_neighbours():
        #     try:
        #         r = patch(s, 'api_1_0.routes', json=msg, auth=HTTPBearerAuth(create_access_token('root')))
        #         if r[1] != 204:
        #             logger.error(f"Unable to send new routing information to node {s}. {r[1]}, {r[0]}")
        #     except Exception as e:
        #         logger.error(
        #             f"Exception raised while trying to send new routing information to node {s}. Exception: {e}")
        return True
    else:
        return False


def process_catalog_route_table(app=None):
    ctx = None
    if app:
        ctx = app.app_context()
        ctx.push()
        try:
            if table_routing_process(discover_new_neighbours=True, check_current_neighbours=True):
                db.session.commit()
            check_catalog()
            db.session.commit()
        finally:
            if ctx:
                ctx.pop()


