import json
import logging
import threading
import typing as t
import uuid
from types import TracebackType
from typing import Optional, Type

from dimensigon.domain.entities import Server, Route, Gate
from dimensigon.domain.entities.server import RouteContainer
from dimensigon.network.low_level import check_host, async_check_host
from dimensigon.use_cases.helpers import get_root_auth
from dimensigon.utils import asyncio
from dimensigon.utils.helpers import convert
from dimensigon.utils.typos import Id
from dimensigon.web import network as ntwrk, db

logger = logging.getLogger('dimensigon.routing')


class _RLock(threading._RLock):

    def __enter__(self) -> bool:
        logger.log(1, "lock acquired")
        return super().__enter__()

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]) -> Optional[bool]:
        db.session.commit()
        logger.log(1, "lock released")
        return super().__exit__(exc_type, exc_val, exc_tb)


_lock = _RLock()

MAX_COST = 99999


def check_gates(server, timeout=2, retries=1, delay=0.5) -> t.Union[RouteContainer, Route]:
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
        if check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries, delay=delay, timeout=timeout):
            return server.route

    for gate in server.gates:
        if gate != server.route.gate:
            if (gate.ip and not gate.ip.is_loopback) or (gate.dns and gate.dns != 'localhost'):
                if check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries, delay=1, timeout=timeout):
                    return RouteContainer(None, gate, 0)


async def async_check_gates(server, timeout=2, retries=1, delay=0.5) -> t.Union[RouteContainer, Route]:
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
        if await async_check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries, delay=delay,
                                  timeout=timeout):
            return server.route

    for gate in server.gates:
        if gate != server.route.gate:
            if (gate.ip and not gate.ip.is_loopback) or (gate.dns and gate.dns != 'localhost'):
                if await async_check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries, delay=1,
                                          timeout=timeout):
                    return RouteContainer(None, gate, 0)


def set_route(server: Server, route: RouteContainer):
    with _lock:
        server.set_route(route)


def format_routes_message(routes: t.Dict[Server, RouteContainer] = None) -> t.Tuple[t.List, t.List]:
    if routes:
        iterator = routes.items()
    else:
        iterator = [(r.destination, r) for r in Route.query.all()]
    msg = []
    debug_msg = []
    for d, r in iterator:
        msg.append(
            dict(destination_id=str(d.id),
                 proxy_server_id=str(getattr(r.proxy_server, 'id')) if getattr(r.proxy_server, 'id',
                                                                               None) else None,
                 gate_id=str(getattr(r.gate, 'id')) if getattr(r.gate, 'id', None) else None,
                 cost=r.cost))

        debug_msg.append(dict(destination=d.name,
                              proxy_server=getattr(r.proxy_server, 'name') if getattr(r.proxy_server, 'name',
                                                                                      None) else None,
                              gate=str(r.gate) if r.gate else None,
                              cost=r.cost))

    return msg, debug_msg


async def async_send_routes(routes=None, auth=None, servers=None, exclude=None):
    if not servers:
        servers = Server.get_neighbours(exclude=exclude)
    if servers:
        logger.debug(f"Sending route information to the following nodes: {', '.join([s.name for s in servers])}")
    else:
        logger.debug(f"No servers to send new routing information")

    msg, debug_msg = format_routes_message(routes)

    aw = [ntwrk.async_patch(s, view_or_url='api_1_0.routes',
                            json={'server_id': Server.get_current().id, 'route_list': msg},
                            auth=auth or get_root_auth(), timeout=20) for s
          in servers]

    rs = await asyncio.gather(*aw)

    for r, s in zip(rs, servers):
        if not r.ok:
            logger.warning(f"Error while trying to send route data to node {s}: {r}")
        else:
            logger.debug(f"New routes sent to {s}: {json.dumps(debug_msg, indent=2)}")


async def _async_set_current_neighbours(neighbours: t.List[Server] = None,
                                        changed_routes: t.Dict[Server, RouteContainer] = None) -> t.List[Server]:
    """ checks and sets neighbours

    Args:
        neighbours: list of neighbours
        changed_routes: reference to a dict which will be populated with new routes

    Returns:
        list of servers which are not neighbours anymore
    """
    not_neighbours_anymore = []

    if neighbours is None:
        neighbours = Server.get_neighbours()

    if neighbours:
        logger.debug(f"Checking current neighbours: " + ', '.join([str(s) for s in neighbours]))
        resp = await asyncio.gather(*[async_check_gates(server) for server in neighbours])
        for route, server in zip(resp, neighbours):
            if isinstance(route, RouteContainer):
                server.set_route(route)
                if changed_routes is not None:
                    changed_routes[server] = route
            elif route is None:
                not_neighbours_anymore.append(server)
                rc = RouteContainer(None, None, None)
                server.set_route(rc)
                if changed_routes is not None:
                    changed_routes[server] = rc
    return not_neighbours_anymore


async def _async_discover_new_neighbours(servers: t.List[Server] = None,
                                         changed_routes: t.Dict[Server, RouteContainer] = None) -> t.List[Server]:
    new_neighbours = []

    if servers is None:
        servers = Server.get_not_neighbours()

    if servers:
        logger.debug(
            f"Checking new neighbours: " + ', '.join([str(s) for s in servers]))
        resp = await asyncio.gather(*[async_check_gates(server) for server in servers])
        for new_route, server in zip(resp, servers):
            if new_route:
                server.set_route(new_route)
                new_neighbours.append(server)
                changed_routes[server] = new_route
        if new_neighbours:
            logger.info(f'New neighbours found: ' + ', '.join([str(s) for s in new_neighbours]))

    return new_neighbours


def _route_table_merge(data: t.Dict[Server, ntwrk.Response]):
    changed_routes: t.Dict[Server, RouteContainer] = {}
    temp_table_routes: t.Dict[uuid.UUID, t.List[RouteContainer]] = {}
    me = Server.get_current()
    for s, resp in data.items():
        if resp.code == 200:
            server_id = resp.msg.get('server_id', None) or resp.msg.get('server').get('id')
            likely_proxy_server_entity = db.session.query(Server).get(server_id)
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
            logger.error(f"Error while connecting with {s}. Error: {resp[1]}, {resp[0]}")

    # Select new routes based on neighbour routes
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

    data = {}
    for server, temp_route in changed_routes.items():
        data.update({str(server): {'proxy_server': str(temp_route.proxy_server), 'gate': str(temp_route.gate),
                                   'cost': str(temp_route.cost)}})
    return changed_routes


async def async_update_route_table_cost(discover_new_neighbours=False, check_current_neighbours=False, retries=2,
                                        timeout_conn=5) -> t.Dict[Server, RouteContainer]:
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

    with _lock:
        logger.debug('Updating routing table')
        neighbours = Server.get_neighbours()
        not_neighbours = Server.get_not_neighbours()

        changed_routes: t.Dict[Server, RouteContainer] = {}

        not_neighbours_anymore = []
        new_neighbours = []

        aws = []
        if check_current_neighbours:
            aws.append(_async_set_current_neighbours(neighbours, changed_routes))
        if discover_new_neighbours:
            aws.append(_async_discover_new_neighbours(not_neighbours, changed_routes))

        res = await asyncio.gather(*aws)

        if check_current_neighbours:
            not_neighbours_anymore = res.pop(0)
        if discover_new_neighbours:
            new_neighbours = res.pop(0)

        if len(not_neighbours_anymore) > 0:
            logger.info(
                f"Lost direct connection to the following nodes: " + ', '.join(
                    [str(s) for s in not_neighbours_anymore]))

        # remove routes whose proxy_server is a node that is not a neighbour
        query = Route.query.filter(
            Route.proxy_server_id.in_([s.id for s in list(set(not_neighbours).union(set(not_neighbours_anymore)))]))
        for route in query.all():
            route.proxy_server = None
            route.cost = None
            changed_routes[route.destination] = RouteContainer(None, None, None)

        # update neighbour list
        neighbours = list(set(neighbours).union(set(new_neighbours)) - set(not_neighbours_anymore))
        if new_neighbours or not_neighbours_anymore:
            logger.info(f"New Neighbour list: {', '.join([str(s) for s in neighbours])}")

        responses = await asyncio.gather(
            *[ntwrk.async_get(server, 'api_1_0.routes', auth=get_root_auth(), timeout=10) for server in neighbours])

        cr = _route_table_merge(dict(zip(neighbours, responses)))
        changed_routes.update(cr)

    return changed_routes


def update_route_table_from_data(new_routes: t.Dict, auth=None) -> t.Dict[Server, RouteContainer]:
    with _lock:
        likely_proxy_server = Server.query.get(new_routes.get('server_id'))
        changed_routes = {}
        me = Server.get_current()
        if not likely_proxy_server:
            logger.warning(f"Server id still '{new_routes.get('server_id')}' not created.")
            return changed_routes
        debug_new_routes = []
        r = new_routes.get('route_list', [])
        r.sort(key=lambda x: x.get('cost') or MAX_COST, reverse=True)
        for new_route in r:
            target_server = Server.query.get(new_route.get('destination_id'))
            proxy_server = Server.query.get(new_route.get('proxy_server_id'))
            gate = Gate.query.get(new_route.get('gate_id'))
            debug_new_route = dict(destination=getattr(target_server, 'name', new_route.get('destination_id')),
                                   proxy_server=getattr(proxy_server, 'name', new_route.get('proxy_server_id')),
                                   gate=str(gate) if gate else new_route.get('gate_id'),
                                   cost=new_route.get('cost'))
            debug_new_routes.append(debug_new_route)
            if target_server is None:
                logger.warning(f"Destination server unknown {new_route.get('destination_id')}")
                continue

            if target_server == me:
                # check if server has detected me as a neighbour
                if new_route.get('cost') == 0:
                    # check if I do not have it as a neighbour yet
                    if likely_proxy_server.route.cost != 0:
                        # check if I have a gate to contact with it
                        route = check_gates(likely_proxy_server)
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
                    if target_server.route.cost is not None:
                        # I do have access through proxy, check route
                        cost, time = ntwrk.ping(target_server, me, retries=1, timeout=15)  # check my route
                    else:
                        cost, time = None, None

                    if cost is not None:
                        # likely proxy does not reach destination but I reach it. Send route
                        if new_route.get('cost') is None:
                            resp = ntwrk.patch(likely_proxy_server, 'api_1_0.routes',
                                               json=dict(server_id=str(me.id),
                                                         route_list=[target_server.route.to_json()]),
                                               auth=auth or get_root_auth())
                            if not resp.ok:
                                logger.warning(f'Unable to send route to {target_server}: {resp}')
                        # if new route has less cost than actual route, take it as my new route
                        elif ((new_route.get('cost') or 999999) + 1) < cost:
                            rc = RouteContainer(likely_proxy_server, None, new_route.get('cost') + 1)
                            target_server.set_route(rc)
                            changed_routes.update({target_server: rc})
                    else:
                        # me does not reaches target_server
                        # if new route reaches the destination take it as a new one
                        if new_route.get('cost') == 0 and new_route.get('gate_id') is not None:
                            rc = RouteContainer(likely_proxy_server, None, 1)
                        elif new_route.get('cost') is not None and proxy_server is not None:
                            rc = RouteContainer(likely_proxy_server, None, new_route.get('cost') + 1)
                        else:
                            # neither my route and the new route has access to the destination
                            rc = RouteContainer(None, None, None)
                        if rc.proxy_server != target_server.route.proxy_server \
                                or rc.gate != target_server.route.gate \
                                or rc.cost != target_server.route.cost:
                            target_server.set_route(rc)
                            changed_routes.update({target_server: rc})
                else:
                    # target_server reached through me as a proxy from likely_proxy
                    pass

    logger.debug(
        f"New routes received from {likely_proxy_server.name}: {json.dumps(debug_new_routes, indent=2)}")
    # if changed_routes:
    #     Parameter.set('routing_last_refresh', get_now())
    return changed_routes


async def async_update_routes_send(discover_new_neighbours=False, check_current_neighbours=False,
                                   send=True, send_full_routes=False,
                                   retries=2, timeout_conn=5):
    # first, update route table
    changed_routes = await async_update_route_table_cost(discover_new_neighbours=discover_new_neighbours,
                                                         check_current_neighbours=check_current_neighbours,
                                                         retries=retries,
                                                         timeout_conn=timeout_conn)

    # send route information
    if send and len(changed_routes) > 0 or send_full_routes:
        await async_send_routes(False if send_full_routes else changed_routes, get_root_auth())


async def async_remove_neighbour_send(server: t.Union[Id, Server], auth, servers=None):
    if not isinstance(server, Server):
        server = Server.query.get(server)
    with _lock:
        server.set_route(RouteContainer(None, None, None))
        lost_routes = Route.query.filter_by(proxy_server=server).count()

        changed_routes = {}

        if lost_routes:
            changed_routes = await async_update_route_table_cost(discover_new_neighbours=False,
                                                                 check_current_neighbours=False)
    changed_routes.update({server: RouteContainer(None, None, None)})
    await async_send_routes(changed_routes, auth, servers=servers)


async def async_check_set_neighbour_send(server, auth):
    if getattr(server.route, 'cost', None) is None:
        new_route = await async_check_gates(server)
        if isinstance(new_route, RouteContainer):
            set_route(server, new_route)
            await async_send_routes({server: new_route}, auth=auth, exclude=server)
