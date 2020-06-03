import datetime
import json
import logging
import os
import typing as t
import uuid
from collections import namedtuple

import aiohttp
import requests
from bs4 import BeautifulSoup
from flask import current_app
from pkg_resources import parse_version

from dm import __version__ as dm_version, defaults
from dm.domain.entities import Server, Catalog, Route
from dm.network.low_level import check_host
from dm.use_cases.helpers import get_auth_root
from dm.use_cases.use_cases import run_elevator, get_software, upgrade_catalog_from_server
from dm.utils import asyncio
from dm.utils.asyncio import create_task
from dm.utils.helpers import get_filename_from_cd, convert
from dm.web import db
from dm.web.decorators import run_as
from dm.web.network import async_get, ping, get

logger = logging.getLogger('dm.background')
routing_logger = logging.getLogger('dm.background.routing')
catalog_logger = logging.getLogger('dm.background.catalog')
upgrader_logger = logging.getLogger('dm.background.upgrader')



@run_as('root')
def process_get_new_version_from_gogs(app=None):
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
        gogs_versions = {}

        html_content = r.text
        soup = BeautifulSoup(html_content, 'html.parser')
        for li in soup.find(id='release-list').find_all('li'):
            version = li.h4.a.get_text(strip=True)
            uris = [a.attrs['href'] for a in li.find('div', class_='download').find_all('a') if
                    a.attrs['href'].endswith('tar.gz')]
            if len(uris) > 0:
                gogs_versions.update({parse_version(version): uris[0]})
        current_version = parse_version(dm_version)
        new_versions = [gogs_ver for gogs_ver in gogs_versions if gogs_ver > current_version]

        if new_versions:
            new_version = max(new_versions)
            upgrader_logger.info(f"Downloading version {new_version} from outside world")

            r = requests.get(base_url + gogs_versions[new_version],
                             verify=current_app.config['SSL_VERIFY'])
            filename = get_filename_from_cd(
                r.headers.get(
                    'content-disposition')) or f"dimensigon-{gogs_versions[new_version].rsplit('/', 1)[-1]}"
            os.makedirs(os.path.join(current_app.config['SOFTWARE_REPO'], 'dimensigon'), exist_ok=True)
            file = os.path.join(current_app.config['SOFTWARE_REPO'], 'dimensigon', filename)
            try:
                open(file, 'wb').write(r.content)
            except Exception as e:
                upgrader_logger.exception(f"Unable to save {file}")
            else:
                run_elevator(file, new_version, upgrader_logger)
    else:
        upgrader_logger.debug(f"No version to upgrade")


TempRoute = namedtuple('TempRoute', ['proxy_server', 'gate', 'cost'])


def update_table_routing_cost(discover_new_neighbours=False, check_current_neighbours=False, retries=2, timeout=10) -> \
        t.Dict[
            Server, TempRoute]:
    """Gets route tables of all neighbours and updates its own table based on jump weights.
    Needs a Flask App Context to run.

    Parameters
    ----------
    discover_new_neighbours:
        tries to discover new neighbours
    check_current_neighbours:
        checks if current neighbours are still neighoburs
    retries:
        number of times it will try to reach destination
    timeout:
        time in seconds to stop waiting for connection

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
            cost, time = ping(server, me, retries=retries, timeout=timeout)
            if cost is None:
                default_gate = server.route.gate
                temp = [None, None, None]
                # try another gate
                for gate in server.gates:
                    # check not to connect with localhost gate from current node and not to check already checked gate
                    if gate != default_gate and ((gate.ip and not gate.ip.is_loopback) or (
                            gate.dns and gate.dns != 'localhost')):
                        if check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries, delay=0.2,
                                      timeout=timeout):
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
        routing_logger.info(
            f"Lost direct connection to the following nodes: " + ', '.join([str(s) for s in not_neighbours_anymore]))

    new_neighbours = []
    if discover_new_neighbours:
        routing_logger.debug(
            f"Checking new neighbours: " + ', '.join([str(s) for s in not_neighbours_anymore]))
        for server in not_neighbours:
            for gate in server.gates:
                if (gate.ip and not gate.ip.is_loopback) or (gate.dns and gate.dns != 'localhost'):
                    if check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries, delay=1,
                                  timeout=timeout):

                        if server.route:
                            server.route.gate = gate
                            server.route.proxy_server = None
                            server.route.cost = 0
                            new_neighbours.append(server)
                        else:
                            r = Route(destination=server, proxy_server=None, gate=gate, cost=0)
                            db.session.add(r)
                        changed_routes[server] = TempRoute(None, server.route.gate, server.route.cost)
                        break
        if new_neighbours:
            routing_logger.info(f'New neighbours found: ' + ', '.join([str(s) for s in new_neighbours]))

    pool_responses = []
    neighoburs = Server.get_neighbours()
    if new_neighbours or not_neighbours_anymore:
        routing_logger.info(f"New Neighbour list {', '.join([str(s) for s in neighoburs])}")

    for server in neighoburs:
        pool_responses.append(get(server, 'api_1_0.routes', auth=get_auth_root()))

    for resp in pool_responses:
        if resp.code == 200:

            likely_proxy_server_entity = db.session.query(Server).get(resp.msg.get('server_id'))
            routing_logger.debug(
                f"route list got from server {likely_proxy_server_entity}: {json.dumps(resp.msg['route_list'], indent=4)}")

            for route_json in resp.msg['route_list']:
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

async def _get_neighbour_catalog_data_mark() -> t.Dict[Server, t.Tuple[t.Any, int]]:
    server_responses = {}
    servers = Server.get_neighbours()
    catalog_logger.debug(f"Neighbour servers to check: {[s.name for s in servers]}")
    auth = get_auth_root()

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
            ssl=current_app.config['SSL_VERIFY'])) as session:
        for server in servers:

                server_responses[server] = create_task(async_get(server, 'root.healthcheck', session=session,
                                                           auth=auth))

        for server, future in server_responses.items():
            server_responses[server] = await future

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


def upgrade_version(data: t.Dict[Server, t.Tuple[t.Any, int]]):
    mayor_version, mayor_server = None, None
    for server, response in data.items():
        if response[1] == 200 and 'version' in response[0]:
            remote_version = parse_version(response[0]['version'])
            if remote_version > parse_version(dm_version):
                if mayor_version is None or mayor_version < remote_version:
                    mayor_version, mayor_server = remote_version, server
    if mayor_version:
        catalog_logger.info(f'Found mayor version on server {mayor_server}. Upgrading version first')
        file, v = get_software(mayor_server, get_auth_root())
        if file:
            run_elevator(file, mayor_version, catalog_logger)
            return True
    return False


def update_catalog(data: t.Dict[Server, t.Tuple[t.Any, int]]):
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
                            f"Server {server} has different software version {response[0]['version']}")
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
            catalog_logger.debug(f"No server with higher catalog found")


@run_as('root')
def process_catalog_route_table(app=None):
    # app will be used for the run_as decorator
    if update_table_routing_cost(discover_new_neighbours=True, check_current_neighbours=True):
        db.session.commit()
    catalog_logger.debug("Starting check catalog from neighbours")
    data = asyncio.run(_get_neighbour_catalog_data_mark())
    # check version upgrade before catalog upgrade to match database revision
    if not upgrade_version(data):
        update_catalog(data)
    db.session.commit()



