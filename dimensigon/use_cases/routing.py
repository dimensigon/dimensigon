import json
import logging
import queue
import random
import threading
import typing as t
import uuid
from types import TracebackType
from typing import Optional, Type

from dimensigon.domain.entities import Server, Route, Gate
from dimensigon.domain.entities.route import RouteContainer
from dimensigon.network.low_level import check_host, async_check_host
from dimensigon.use_cases.helpers import get_root_auth
from dimensigon.utils import asyncio
from dimensigon.utils.helpers import convert, is_iterable_not_string, is_valid_uuid, format_exception
from dimensigon.utils.typos import Id
from dimensigon.web import network as ntwrk, db

logger = logging.getLogger('dm.routing')


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


def check_gates(server, timeout=5, retries=1, delay=0.5) -> t.Union[RouteContainer, Route]:
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
    if server.route and server.route.gate:
        gate = server.route.gate
        if check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries, delay=delay, timeout=timeout):
            return server.route

    for gate in server.gates:
        if server.route and gate != server.route.gate:
            if (gate.ip and not gate.ip.is_loopback) or (gate.dns and gate.dns != 'localhost'):
                if check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries, delay=1, timeout=timeout):
                    return RouteContainer(None, gate, 0)


async def async_check_gates(server, timeout=5, retries=1, delay=1) -> t.Union[RouteContainer, Route]:
    """checks if a server is neighbour

    Args:
        server: server to discover as a new neighbour
        timeout: timeout socket
        retries: number of times to try to connect to the socket
        delay: time in seconds between retries

    Returns:
        returns Route if no change. This means that gate in inventory is still up.
                RouteContainer if there is an available gate to connect
                None if no gate to connect
    """

    # check current gate
    if server.route and server.route.gate:
        gate = server.route.gate
        if await async_check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries + 1, delay=delay,
                                  timeout=timeout):
            return server.route

    for gate in server.gates:
        if server.route and gate != server.route.gate:
            if (gate.ip and not gate.ip.is_loopback) or (gate.dns and gate.dns != 'localhost'):
                if await async_check_host(host=gate.dns or str(gate.ip), port=gate.port, retry=retries,
                                          delay=1,
                                          timeout=timeout):
                    return RouteContainer(None, gate, 0)


def set_route(server: Server, route: RouteContainer):
    with _lock:
        server.set_route(route)
        db.session.add(server.route)
        db.session.commit()


def format_routes_message(routes: t.Dict[t.Union[Id, Server], RouteContainer] = None) -> t.Tuple[t.List, t.List]:
    if routes:
        iterator = routes.items()
    else:
        iterator = [(r.destination, r) for r in Route.query.all()]
    msg = []
    debug_msg = []
    for d, r in iterator:
        msg.append(
            dict(destination_id=getattr(d, 'id', d),
                 proxy_server_id=str(getattr(r.proxy_server, 'id')) if getattr(r.proxy_server, 'id',
                                                                               None) else None,
                 gate_id=str(getattr(r.gate, 'id')) if getattr(r.gate, 'id', None) else None,
                 cost=r.cost))

        debug_msg.append(dict(destination=getattr(d, 'name', d),
                              proxy_server=getattr(r.proxy_server, 'name') if getattr(r.proxy_server, 'name',
                                                                                      None) else None,
                              gate=str(r.gate) if r.gate else None,
                              cost=r.cost))

    return msg, debug_msg


async def async_send_routes(routes=None, auth=None, servers=None, exclude=None):
    if not servers:
        servers = Server.get_neighbours(exclude=exclude)
    msg, debug_msg = format_routes_message(routes)

    c_exclude = []
    if logger.level <= logging.DEBUG:
        if exclude:
            if is_iterable_not_string(exclude):
                c_exclude = [Server.query.get(e) if not isinstance(e, Server) else e for e in exclude]
            else:
                c_exclude = [Server.query.get(exclude) if not isinstance(exclude, Server) else exclude]
            log_msg = f" (Excluded nodes: {', '.join([getattr(e, 'name', e) for e in c_exclude])}):"
        else:
            log_msg = ''

        if servers:
            log_msg = f"Sending route information to the following nodes: {', '.join([s.name for s in servers])}" \
                      f"{log_msg}\n{json.dumps(debug_msg, indent=2)}"
        else:
            log_msg = f"No servers to send new routing information:{log_msg}\n{json.dumps(debug_msg, indent=2)}"

        logger.debug(log_msg)

    exclude_ids = list(set([s.id for s in servers]).union([getattr(e, 'id', e) for e in c_exclude]))

    aw = [ntwrk.async_patch(s, view_or_url='api_1_0.routes',
                            json={'server_id': Server.get_current().id, 'route_list': msg, 'exclude': exclude_ids},
                            auth=auth or get_root_auth()) for s
          in servers]

    rs = await asyncio.gather(*aw, return_exceptions=True)

    for r, s in zip(rs, servers):
        if isinstance(r, Exception):
            logger.warning(
                f"Error while trying to send route data to node {s}: "
                f"{format_exception(r)}")
        elif not r.ok:
            if r.exception:
                logger.warning(
                    f"Error while trying to send route data to node {s}: "
                    f"{format_exception(r.exception)}")
            else:
                logger.warning(f"Error while trying to send route data to node {s}: {r}")


async def _async_set_current_neighbours(neighbours: t.List[Server] = None,
                                        changed_routes: t.Dict[Server, RouteContainer] = None) -> t.List[Server]:
    """Function checks and sets neighbours

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
        resp = await asyncio.gather(*[async_check_gates(server) for server in servers], return_exceptions=True)
        for new_route, server in zip(resp, servers):
            if new_route:
                server.set_route(new_route)
                new_neighbours.append(server)
                changed_routes[server] = new_route

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
            proxy_server: Server = db.session.query(Server).get(min_route.proxy_server)
            cost = min_route.cost
            if route.proxy_server != proxy_server or route.cost != cost:
                rc = RouteContainer(proxy_server, None, cost)
                route.set_route(rc)
                changed_routes[route.destination] = rc
                db.session.add(route)

    data = {}
    for server, temp_route in changed_routes.items():
        data.update({str(server): {'proxy_server': str(temp_route.proxy_server), 'gate': str(temp_route.gate),
                                   'cost': str(temp_route.cost)}})
    return changed_routes


async def async_update_route_table_cost(discover_new_neighbours=False, check_current_neighbours=False, retries=2,
                                        timeout_conn=5, max_num_discovery=None) -> t.Dict[Server, RouteContainer]:
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
            if neighbours:
                logger.debug(f"Checking current neighbours: " + ', '.join([str(s) for s in neighbours]))
                aws.append(_async_set_current_neighbours(neighbours, changed_routes))
            else:
                logger.debug(f"No neighbour to check")

        if discover_new_neighbours:
            if not_neighbours[:max_num_discovery]:
                rs = list(not_neighbours)
                random.shuffle(rs)
                target = rs[:max_num_discovery]
                target.sort(key=lambda s: s.name)
                logger.debug(
                    f"Checking new neighbours{f' (limited to {max_num_discovery})' if max_num_discovery else ''}: "
                    + ', '.join([str(s) for s in target]))
                aws.append(_async_discover_new_neighbours(target, changed_routes))
            else:
                logger.debug("No new neighbours to check")

        res = await asyncio.gather(*aws, return_exceptions=False)

        if check_current_neighbours and neighbours:
            not_neighbours_anymore = res.pop(0)
            if not_neighbours_anymore:
                logger.info(
                    f"Lost direct connection to the following nodes: " + ', '.join(
                        [str(s) for s in not_neighbours_anymore]))
        if discover_new_neighbours and not_neighbours[:max_num_discovery]:
            new_neighbours = res.pop(0)
            if new_neighbours:
                logger.info(f'New neighbours found: ' + ', '.join([str(s) for s in new_neighbours]))
            else:
                logger.debug("No new neighbours found")

        # remove routes whose proxy_server is a node that is not a neighbour
        query = Route.query.filter(
            Route.proxy_server_id.in_([s.id for s in list(set(not_neighbours).union(set(not_neighbours_anymore)))]))
        rc = RouteContainer(None, None, None)
        for route in query.all():
            route.set_route(rc)
            changed_routes[route.destination] = rc

        # update neighbour list
        neighbours = list(set(neighbours).union(set(new_neighbours)) - set(not_neighbours_anymore))

        if neighbours:
            logger.debug(f"Getting routing tables from {', '.join([str(s) for s in neighbours])}")
            responses = await asyncio.gather(
                *[ntwrk.async_get(server, 'api_1_0.routes', auth=get_root_auth()) for server in neighbours])

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
                    if likely_proxy_server.route and likely_proxy_server.route.cost != 0:
                        # check if I have a gate to contact with it
                        route = check_gates(likely_proxy_server)
                        if isinstance(route, RouteContainer):
                            changed_routes[likely_proxy_server] = route
                            likely_proxy_server.set_route(route)
                        elif route is None:
                            if likely_proxy_server.route and likely_proxy_server.route.cost is not None:
                                changed_routes[likely_proxy_server] = RouteContainer(None, None, None)
                                likely_proxy_server.set_route(changed_routes[likely_proxy_server])
            else:
                # server may be created without route (backward compatibility)
                if target_server.route is None:
                    target_server.set_route(Route(destination=target_server))
                # process routes whose proxy_server is not me
                if str(me.id) != new_route.get('proxy_server_id'):
                    # check If I reach destination
                    if target_server.route.cost is not None:
                        if new_route.get('cost') is None:
                            #  likely proxy does not reach but I reach it. It might be shutdown unexpectedly?
                            if target_server.route.cost == 0:
                                # check if I still have it as a neighbour
                                route = check_gates(target_server)
                            else:
                                if target_server.route.proxy_server == likely_proxy_server:
                                    route = RouteContainer(None, None, None)
                                else:
                                    # check if I still have access through my proxy
                                    cost, time = ntwrk.ping(target_server, retries=1, timeout=20)
                                    if cost == target_server.route.cost:
                                        # still a valid route
                                        route = target_server.route
                                    elif cost is None:
                                        route = RouteContainer(None, None, None)
                                    else:
                                        route = RouteContainer(target_server.route.proxy_server, None, cost)

                            if isinstance(route, RouteContainer):
                                # gate changed
                                changed_routes[target_server] = route
                                target_server.set_route(route)
                            elif route is None:
                                # no route to host. I've lost contact too
                                changed_routes[target_server] = RouteContainer(None, None, None)
                                target_server.set_route(changed_routes[target_server])
                            else:
                                # still a valid route. Send route to likely_proxy_server to tell it I have access
                                resp = ntwrk.patch(likely_proxy_server, 'api_1_0.routes',
                                                   json=dict(server_id=str(me.id),
                                                             route_list=[target_server.route.to_json()]),
                                                   auth=auth or get_root_auth(), timeout=5)
                                if not resp.ok:
                                    logger.info(f'Unable to send route to {likely_proxy_server}: {resp}')
                        elif target_server.route.proxy_server is not None and \
                                target_server.route.proxy_server == likely_proxy_server:
                            # my proxy is telling me the route has changed
                            rc = RouteContainer(likely_proxy_server, None, new_route.get('cost') + 1)
                            target_server.set_route(rc)
                            changed_routes.update({target_server: rc})
                        elif new_route.get('cost') + 1 < target_server.route.cost:
                            # if new route has less cost than actual route, take it as my new route
                            rc = RouteContainer(likely_proxy_server, None, new_route.get('cost') + 1)
                            target_server.set_route(rc)
                            changed_routes.update({target_server: rc})
                    else:
                        # me does not reaches target_server
                        # if new route reaches the destination take it as a new one
                        if (new_route.get('cost') == 0 and new_route.get('gate_id') is not None) or (
                                new_route.get('cost') is not None and proxy_server is not None):
                            rc = RouteContainer(likely_proxy_server, None, new_route.get('cost') + 1)
                        else:
                            # neither my route and the new route has access to the destination
                            rc = RouteContainer(None, None, None)
                        if target_server.route and (
                                rc.proxy_server != target_server.route.proxy_server or
                                rc.gate != target_server.route.gate or
                                rc.cost != target_server.route.cost):
                            target_server.set_route(rc)
                            changed_routes.update({target_server: rc})
                else:
                    # target_server reached through me as a proxy from likely_proxy
                    pass

    query = Route.query.filter(
        Route.proxy_server_id.in_([s.id for s, r in changed_routes.items() if r.cost is None]))
    rc = RouteContainer(None, None, None)
    for route in query.all():
        route.set_route(rc)
        changed_routes[route.destination] = rc

    logger.debug(
        f"New routes processed from {likely_proxy_server.name}: {json.dumps(debug_new_routes, indent=2)}")
    # if changed_routes:
    #     Parameter.set('routing_last_refresh', get_now())
    return changed_routes


async def async_update_routes_send(discover_new_neighbours=False, check_current_neighbours=False,
                                   send=True, send_full_routes=False, max_num_discovery=None,
                                   retries=2, timeout_conn=5):
    # first, update route table
    changed_routes = await async_update_route_table_cost(discover_new_neighbours=discover_new_neighbours,
                                                         check_current_neighbours=check_current_neighbours,
                                                         retries=retries,
                                                         timeout_conn=timeout_conn,
                                                         max_num_discovery=max_num_discovery)
    # send route information
    if send and len(changed_routes) > 0 or send_full_routes:
        await async_send_routes(False if send_full_routes else changed_routes, get_root_auth())


async def async_remove_neighbour_send(server: t.Union[Id, Server], auth, servers=None):
    if not isinstance(server, Server):
        _server = Server.query.get(server)
    else:
        _server = server

    changed_routes = {}

    if _server:
        with _lock:
            _server.set_route(RouteContainer(None, None, None))
            lost_routes = Route.query.filter_by(proxy_server=_server).count()
            if lost_routes:
                changed_routes = await async_update_route_table_cost(discover_new_neighbours=False,
                                                                     check_current_neighbours=False)
    changed_routes.update({_server or server: RouteContainer(None, None, None)})
    await async_send_routes(changed_routes, auth, servers=servers)


async def async_check_set_neighbour_send(server: t.Union[Id, Server], auth):
    with _lock:
        if not isinstance(server, Server):
            if is_valid_uuid(server):
                server = Server.query.get(server)
            else:
                return
        else:
            if server not in db.session:
                server = db.session.merge(server, load=True)

        if server and server.route and server.route.cost != 0:
            new_route = await async_check_gates(server)
            if isinstance(new_route, RouteContainer):
                logger.debug(f"New neighbour {server} found on keepalive with gate {new_route.gate}")
                server.set_route(new_route)
                await async_send_routes({server: new_route}, exclude=server, auth=auth)


class RouteManager:

    def __init__(self, app, maxsize=None, retain_time=2, start=True):
        self.app = app
        self.queue = queue.Queue(maxsize=maxsize or 10000)
        self._stop = False
        self.buffer: t.Dict[Id, t.Dict] = {}
        self.retain_time = retain_time
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.run, name='route_manager')
        self._change_buffer_lock = threading.RLock()
        self._timer = None
        if start:
            self._thread.start()

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop = True
        self.queue.put('STOP', block=False)
        if self._timer:
            self._timer.cancel()

    def _add2buffer(self, data: t.Union[t.List[t.Dict], t.Dict]):
        with self._change_buffer_lock:
            if isinstance(data, dict):
                self.buffer.update({data['id']: data})
            else:
                self.buffer.update(**{cr['id']: cr for cr in data})
            if self._timer is None:
                self._timer = threading.Timer(interval=self.retain_time, function=self.send_data)
                self._timer.start()

    def put(self, data: t.Union[t.Dict, t.List[t.Dict]], block=True, timeout=None):
        self.queue.put(data, block=block, timeout=timeout)

    def send_data(self):
        with self.app.app_context():
            # time to send data
            neighbours = Server.get_neighbours()
            if neighbours:
                logger.debug(
                    f"Sending route information to the following nodes {', '.join([s.name for s in neighbours])}")

                auth = get_root_auth()
                with self._change_buffer_lock:
                    temp_buffer = dict(self.buffer)
                    self.buffer.clear()
                if logger.level <= logging.DEBUG:
                    logger.debug(f"{json.dumps(temp_buffer.values(), indent=2)}")
                try:
                    responses = self.loop.run_until_complete(
                        ntwrk.parallel_requests(neighbours, 'POST', view_or_url='api_1_0.cluster',
                                                json=list(temp_buffer.values()), auth=auth))
                except Exception as e:
                    logger.error(f"Unable to send route information to neighbours: "
                                 f"{format_exception(e)}")
                    # restore data with new data arrived
                    with self._change_buffer_lock:
                        temp_buffer.update(**self.buffer)
                        self.buffer.clear()
                        self.buffer.update(temp_buffer)
                else:
                    for s, r in zip(neighbours, responses):
                        if not r.ok:
                            logger.warning(f"Unable to send data to {s}: {r}")

                # set timer to launch again on change
                with self._change_buffer_lock:
                    self._timer = None
            else:
                logger.debug(f"No neighbour servers to send route information")
                with self._change_buffer_lock:
                    self._timer = None

    def run(self):
        logger.debug('Starting route manager')
        while not self._stop:
            try:
                item = self.queue.get(block=True, timeout=5)
            except queue.Empty:
                pass
            else:
                if item == 'STOP':
                    break
                elif item:
                    pass
        logger.debug('Stopping route manager')