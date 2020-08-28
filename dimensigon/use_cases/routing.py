import json
import logging
import typing as t
import uuid

from flask import current_app

from dimensigon.domain.entities import Server, Route
from dimensigon.domain.entities.server import RouteContainer
from dimensigon.network.low_level import check_host
from dimensigon.use_cases.helpers import get_auth_root
from dimensigon.utils import asyncio
from dimensigon.utils.cluster_manager import ClusterManager
from dimensigon.utils.helpers import convert
from dimensigon.utils.typos import Id
from dimensigon.web import network as ntwrk, db

_routing_logger = logging.getLogger('dimensigon.routing')
_cluster_logger = logging.getLogger('dimensigon.cluster')


def check_neighbour(server, timeout=2, retries=1) -> t.Union[RouteContainer, Route]:
    """checks if a server is neighbour

    Args:
        server: server to discover as a new neighbour
        timeout: timeout socket
        retries: number of times to try to connect to the socket

    Returns:
        returns Route if no change. This means that gate in inventory is still up.
                RouteContainer if there is an available gate to connect
                None if no gate to connect
    """

    # check current gate
    if server.route.gate:
        gate = server.route.gate
        if check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries, delay=0.5, timeout=timeout):
            return server.route

    for gate in server.gates:
        if gate != server.route.gate:
            if (gate.ip and not gate.ip.is_loopback) or (gate.dns and gate.dns != 'localhost'):
                if check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries, delay=1, timeout=timeout):
                    return RouteContainer(None, gate, 0)


def update_route_table_cost(discover_new_neighbours=False, check_current_neighbours=False, retries=2, timeout_conn=5) -> \
        t.Dict[
            Server, RouteContainer]:
    """Gets route tables of all neighbours and updates its own table based on jump weights.
    Needs a Flask App Context to run.

    Parameters
    ----------
    discover_new_neighbours:
        tries to discover new neighbours
    check_current_neighbours:
        checks if current neighbours are still neighbours
    retries:
        number of times it will try to reach destination
    timeout_conn:
        time in seconds to stop waiting for connection

    Returns
    -------
    None
    """
    # get all neighbours
    temp_table_routes: t.Dict[uuid.UUID, t.List[RouteContainer]] = {}
    changed_routes: t.Dict[Server, RouteContainer] = {}
    me = Server.get_current()
    not_neighbours = Server.get_not_neighbours()
    _routing_logger.debug('Updating routing table')
    not_neighbours_anymore = []
    if check_current_neighbours:
        neighbours = Server.get_neighbours()
        _routing_logger.debug(
            f"Checking current neighbours: " + ', '.join([str(s) for s in neighbours]))
        for server in neighbours:
            route = check_neighbour(server)
            if isinstance(route, RouteContainer):
                changed_routes[server] = route
                server.set_route(route)
            elif route is None:
                not_neighbours_anymore.append(server)
                changed_routes[server] = RouteContainer(None, None, None)
                server.set_route(None, None, None)
    if len(not_neighbours_anymore) > 0:
        _routing_logger.info(
            f"Lost direct connection to the following nodes: " + ', '.join([str(s) for s in not_neighbours_anymore]))

    new_neighbours = []
    if discover_new_neighbours:
        _routing_logger.debug(
            f"Checking new neighbours: " + ', '.join([str(s) for s in not_neighbours]))
        for server in not_neighbours:
            new_route = check_neighbour(server, 2, retries=1)
            if new_route:
                server.set_route(new_route)
                new_neighbours.append(server)
                changed_routes[server] = new_route
        if new_neighbours:
            _routing_logger.info(f'New neighbours found: ' + ', '.join([str(s) for s in new_neighbours]))

    pool_responses = []
    neighbours = Server.get_neighbours()
    if new_neighbours or not_neighbours_anymore:
        _routing_logger.info(f"New Neighbour list {', '.join([str(s) for s in neighbours])}")

    for server in neighbours:
        pool_responses.append(ntwrk.get(server, 'api_1_0.routes', auth=get_auth_root(), timeout=10))

    for resp in pool_responses:
        if resp.code == 200:
            server_id = resp.msg.get('server_id', None) or resp.msg.get('server').get('id')
            likely_proxy_server_entity = db.session.query(Server).get(server_id)
            _routing_logger.debug(
                f"route list got from server {likely_proxy_server_entity}: {json.dumps(resp.msg['route_list'], indent=4)}")

            for route_json in resp.msg['route_list']:
                route_json = convert(route_json)
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
                            RouteContainer(likely_proxy_server_entity.id, None, route_json.cost))
                    elif route_json.cost is None:
                        # remove a routing if gateway cannot reach the destination
                        temp_table_routes[route_json.destination_id].append(
                            RouteContainer(route_json.proxy_server_id, None, None))
        else:
            s = neighbours[pool_responses.index(resp)]
            _routing_logger.error(f"Error while connecting with {s}. Error: {resp[1]}, {resp[0]}")

    # Select new routes based on neighbour routes
    MAX_COST = 9999999
    neighbour_ids = [s.id for s in Server.get_neighbours()]
    for destination_id in filter(lambda s: s not in neighbour_ids, temp_table_routes.keys()):
        route = db.session.query(Route).filter_by(destination_id=destination_id).one_or_none()
        if not route:
            server = Server.query.get(destination_id)
            if not server:
                continue
            else:
                route = Route(destination=server)
        temp_table_routes[destination_id].sort(key=lambda x: x.cost or MAX_COST)
        if len(temp_table_routes[destination_id]) > 0:
            min_route = temp_table_routes[destination_id][0]
            proxy_server = db.session.query(Server).get(min_route.proxy_server)
            cost = min_route.cost
            if route.proxy_server != proxy_server or route.cost != cost:
                route.proxy_server = proxy_server
                route.gate = None
                route.cost = cost
                changed_routes[route.destination] = RouteContainer(route.proxy_server,
                                                                   route.gate,
                                                                   route.cost)
                db.session.add(route)
                break

    data = {}
    for server, temp_route in changed_routes.items():
        data.update({str(server): {'proxy_server': str(temp_route.proxy_server), 'gate': str(temp_route.gate),
                                   'cost': str(temp_route.cost)}})
    _routing_logger.debug(f'Changed routes from neighbours: {json.dumps(data, indent=4)}')
    return changed_routes


async def set_not_a_neighbour(server: t.Union[Id, Server], auth=None, commit=False):
    if not isinstance(server, Server):
        server = Server.query.get(server)
    server.set_route(RouteContainer(None, None, None))
    lost_routes = Route.query.filter_by(proxy_server=server).count()

    changed_routes = {}

    if lost_routes:
        changed_routes = update_route_table_cost(discover_new_neighbours=False, check_current_neighbours=False)
    changed_routes.update({server: RouteContainer(None, None, None)})
    if commit:
        db.session.commit()

    await send_new_routes(changed_routes, auth)


async def send_new_routes(new_routes, auth):
    msg = {'server_id': str(Server.get_current().id),
           'route_list': [
               dict(destination_id=str(d.id),
                    proxy_server_id=str(getattr(r.proxy_server, 'id')) if getattr(r.proxy_server, 'id',
                                                                                  None) else None,
                    gate_id=str(getattr(r.gate, 'id')) if getattr(r.gate, 'id', None) else None,
                    cost=r.cost)
               for d, r in new_routes.items()
           ]}

    ns = Server.get_neighbours(alive=True)
    aw = [ntwrk.async_patch(s, view_or_url='api_1_0.routes', json=msg, auth=auth, timeout=5) for s in ns]

    rs = await asyncio.gather(*aw)

    for r, s in zip(rs, ns):
        if not r.ok:
            _routing_logger.warning(f"Error while trying to send route data to node {s}: {r}")


def update_route_table_from_data(new_routes: t.Dict, auth=None) -> t.Dict[Server, RouteContainer]:
    _routing_logger.debug(f"New routes recived: {json.dumps(new_routes, indent=4)}")
    likely_proxy_server = Server.query.get(new_routes.get('server_id'))
    changed_routes = {}
    me = Server.get_current()
    if not likely_proxy_server:
        _routing_logger.warning(f"Server id still '{new_routes.get('server_id')}' not created.")
        return changed_routes
    for new_route in new_routes.get('route_list', []):
        target_server = Server.query.get(new_route.get('destination_id'))
        if target_server is None:
            _routing_logger.warning(f"Destination server unknown {new_route.get('destination_id')}")
            continue
        if target_server == me:
            # check if server has detected me as a neighbour
            if new_route.get('cost') == 0:
                # check if I do not have it as a neighbour yet
                if likely_proxy_server.route.cost != 0:
                    # check if I have a gate to contact with it
                    route = check_neighbour(likely_proxy_server)
                    if isinstance(route, RouteContainer):
                        changed_routes[likely_proxy_server] = route
                        likely_proxy_server.set_route(route)
                    elif route is None:
                        if likely_proxy_server.route.cost is not None:
                            changed_routes[likely_proxy_server] = RouteContainer(None, None, None)
                            likely_proxy_server.set_route(None, None, None)
        else:
            # server may be created without route (backward compatibility)
            if target_server.route is None:
                target_server.route = Route(destination=target_server)
            # process routes whose proxy_server is not me
            if str(me.id) != new_route.get('proxy_server_id'):
                # my current proxy does not have access
                if target_server.route.proxy_server == likely_proxy_server and new_route.get('cost') is None:
                    cost, time = None, None
                else:
                    cost, time = ntwrk.ping(target_server, me, retries=1, timeout=5)  # check my route

                if cost is not None:
                    # likely proxy does not reach destination but I reach it. Send route
                    if new_route.get('cost') is None:
                        resp = ntwrk.patch(likely_proxy_server, 'api_1_0.routes',
                                           json=dict(server_id=str(me.id),
                                                     route_list=[target_server.route.to_json()]),
                                           auth=auth or get_auth_root())
                        if not resp.ok:
                            _routing_logger.warning(f'Unable to send route to {target_server}: {resp}')
                    # if new route has less cost than actual route, take it as my new route
                    elif ((new_route.get('cost') or 999999) + 1) < cost:
                        rc = RouteContainer(likely_proxy_server, None, new_route.get('cost') + 1)
                        target_server.set_route(rc)
                        changed_routes.update({target_server: rc})
                else:
                    # me does not reaches target_server
                    # if new route reaches the destination take it as a new one
                    if new_route.get('cost') == 0:
                        rc = RouteContainer(likely_proxy_server, None, new_route.get('cost') + 1)
                    elif new_route.get('cost') is not None:
                        proxy_server = Server.query.get(new_route.get('proxy_server_id'))
                        if proxy_server is None:
                            current_app.logger.warning(f"Proxy server unknown {new_route.get('proxy_server_id')}")
                            continue
                        rc = RouteContainer(proxy_server, None, new_route.get('cost') + 1)
                    else:
                        # neither my route and the new route has access to the destination
                        rc = RouteContainer(None, None, None)
                    if rc.proxy_server != target_server.route.proxy_server \
                            or rc.gate != target_server.route.gate \
                            or rc.cost != target_server.route.cost:
                        target_server.set_route(rc)
                        changed_routes.update({target_server: rc})

    # if changed_routes:
    #     Parameter.set('routing_timestamp', get_now())
    return changed_routes


async def send_cluster_register(cr, auth=None, exclude=None):
    servers = Server.get_neighbours(alive=True, exclude=exclude)
    responses = await ntwrk.parallel_requests(servers, 'post',
                                              view_or_url='api_1_0.cluster',
                                              json=cr,
                                              auth=auth,
                                              timeout=10)

    for r, s in zip(responses, servers):
        if not r.ok and _cluster_logger.level <= logging.WARNING:
            _cluster_logger.warning(
                f"Unable to send cluster information to {s}. Response: {r}")


def check_server_alive(server: Server):
    alive_server_ids = [i for i in current_app.cluster if server.id != i and i != Server.get_current().id]
    # check if I have it as a neighbour
    if server.route.cost == 0:
        route = check_neighbour(server)
        if route:
            return True

    # in order to prevent broadcast to everyone, first try a ping
    cost, elapsed = ntwrk.ping(server, Server.get_current(), retries=1, timeout=15)
    if cost is not None:
        return True
    responses = asyncio.run(ntwrk.parallel_requests(alive_server_ids, 'get',
                                                    view_or_url='api_1_0.routes_neighbour',
                                                    view_data=dict(server_id=server.id), timeout=10))
    for r in responses:
        if r.ok:
            if r.msg.get('neighbour'):
                return True
    return False


def update_cluster_status():
    alive_server_ids = current_app.cluster.get_alive()
    updated = False
    for alive_server_id in alive_server_ids:
        if alive_server_id != Server.get_current().id:
            alive = check_server_alive(Server.query.get(Server))
            if not alive:
                current_app.cluster.set_death(alive_server_id)
                updated = True
    return updated


def update_cluster_and_routes(cluster: ClusterManager = None, discover_new_neighbours=False,
                              check_current_neighbours=False,
                              retries=2, timeout_conn=5):
    # first, update route table
    changed_routes = update_route_table_cost(discover_new_neighbours=discover_new_neighbours,
                                             check_current_neighbours=check_current_neighbours,
                                             retries=retries,
                                             timeout_conn=timeout_conn)

    # send route information
    if changed_routes:
        if len(changed_routes) > 0:
            asyncio.run(send_new_routes(changed_routes, get_auth_root()))

    # update cluster based on new routes
    if cluster:
        cr_list = []
        for server, route in changed_routes.items():
            if route.cost is None and server.id in cluster:
                alive = check_server_alive(server)
                if not alive:
                    cr_list.append(cluster.set_death(server.id))
            if route.cost is not None and server.id not in cluster:
                cr_list.append(cluster.set_alive(server.id))
        # send cluster information
        if cr_list:
            asyncio.run(send_cluster_register(cr_list, get_auth_root()))
    db.session.commit()
