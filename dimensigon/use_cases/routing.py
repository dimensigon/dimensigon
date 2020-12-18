import asyncio
import datetime as dt
import json
import logging
import random
import threading
import time
import typing as t
import uuid

from sqlalchemy import orm
from sqlalchemy.orm import sessionmaker

from dimensigon import defaults
from dimensigon.domain.entities import Server, Route, Gate, Parameter
from dimensigon.domain.entities.route import RouteContainer
from dimensigon.network.low_level import check_host, async_check_host
from dimensigon.use_cases.mptools import Worker, MPQueue
from dimensigon.use_cases.mptools_events import BaseEvent
from dimensigon.utils.helpers import convert, is_iterable_not_string, format_exception, get_now
from dimensigon.utils.typos import Id
from dimensigon.web import network as ntwrk, errors, get_root_auth

if t.TYPE_CHECKING:
    from dimensigon.core import Dimensigon

MAX_COST = 99999


class RouteEvent(BaseEvent):
    """Route related Event"""


class InitialRouteSet(RouteEvent):
    """Event published when route inital process has completed"""


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


class RouteManager(Worker):
    ###########################
    # START Class Inheritance #
    def init_args(self, dimensigon: 'Dimensigon', maxsize=None, refresh_interval=defaults.ROUTE_REFRESH_PERIOD,
                  send_interval=defaults.ROUTE_SEND_PERIOD):
        self.dm = dimensigon
        self.Session = sessionmaker(bind=self.dm.engine)
        self.queue = MPQueue(maxsize=maxsize or 10000)
        self._changed_routes: t.Dict[Id, t.Dict] = {}
        self.refresh_interval = refresh_interval
        self.send_interval = send_interval
        self._loop = asyncio.new_event_loop()

    def startup(self):
        def refresh():
            self.refresh_table(discover_new_neighbours=True, check_current_neighbours=True, max_num_discovery=5)
            self._timer = threading.Timer(interval=self.refresh_interval, function=refresh)
            self._timer.start()

        self.session = self._create_session()
        self._timer = threading.Timer(interval=self.refresh_interval, function=refresh)
        self._timer.start()
        self._next_send = time.time() + self.send_interval

    def shutdown(self):
        self.queue.close()
        self.queue.join_thread()
        self.session.close()
        if self._timer:
            self._timer.cancel()
            self._timer.join()

    def _main_loop(self):
        with self.dm.flask_app.app_context():
            last_shutdown = Parameter.get('last_graceful_shutdown')

            try:
                last_shutdown = dt.datetime.strptime(last_shutdown, defaults.DATETIME_FORMAT)
            except:
                last_shutdown = get_now()
            else:
                last_shutdown = last_shutdown

            if self.dm.config.force_scan or last_shutdown < (get_now() - dt.timedelta(seconds=self.refresh_interval)):
                scan = True
            else:
                scan = False
            changed_routes = self._loop.run_until_complete(
                self._async_refresh_route_table(discover_new_neighbours=scan, check_current_neighbours=scan,
                                                max_num_discovery=None))
            self.session.commit()
            self.publish_q.safe_put(InitialRouteSet())

            super()._main_loop()

            Parameter.set('last_graceful_shutdown', get_now().strftime(defaults.DATETIME_FORMAT))

    def main_func(self, *args, **kwargs):
        item = self.queue.safe_get()
        try:
            if item:

                if isinstance(item, tuple) and item[0] == 'REFRESH':
                    changed_routes = self._loop.run_until_complete(self._async_refresh_route_table(*item[1:]))
                elif isinstance(item, tuple) and item[0] == 'NEW':
                    changed_routes = self._new_node_in_cluster(*item[1:])
                elif isinstance(item, tuple) and item[0] == 'REMOVE':
                    changed_routes = self._remove_node_from_cluster(*item[1:])
                else:
                    changed_routes = self._update_route_table_from_data(item)
                if changed_routes:
                    self.session.commit()
                self._changed_routes.update(changed_routes)
            if time.time() > self._next_send:
                if self._changed_routes:
                    self._loop.run_until_complete(self._send_routes())
                self._next_send = time.time() + self.send_interval
        except Exception as e:
            self.logger.exception(f"Error processing item {item}")
            self.session.rollback()

    # END Class Inheritance #
    #########################

    ############################
    # INIT Interface functions #
    def refresh_table(self, discover_new_neighbours, check_current_neighbours, max_num_discovery):
        self.queue.safe_put(('REFRESH', discover_new_neighbours, check_current_neighbours, max_num_discovery))

    def new_node_in_cluster(self, server_id, routes):
        self.queue.safe_put(('NEW', server_id, routes))

    def remove_node_from_cluster(self, server_id):
        self.queue.safe_put(('REMOVE', server_id))

    def new_routes(self, new_routes):
        self.queue.safe_put(new_routes)

    # END Interface functions  #
    ############################

    ##############################
    # INNER methods & attributes #
    def _create_session(self):
        self.Session = sessionmaker(bind=self.dm.engine, autoflush=False)
        return self.Session()

    @property
    def server(self) -> Server:
        if getattr(self, '_server', None) is None:
            self._server = self.session.query(Server).filter_by(_me=1, deleted=0).one_or_none()
        return self._server

    @property
    def server_query(self):
        return self.session.query(Server).filter_by(deleted=0) if self.session else None

    @property
    def gate_query(self):
        return self.session.query(Gate).filter_by(deleted=0) if self.session else None

    def _route_table_merge(self, data: t.Dict[Server, ntwrk.Response]):
        changed_routes: t.Dict[Server, RouteContainer] = {}
        temp_table_routes: t.Dict[uuid.UUID, t.List[RouteContainer]] = {}
        for s, resp in data.items():
            if resp.code == 200:
                server_id = resp.msg.get('server_id', None) or resp.msg.get('server').get('id')
                likely_proxy_server_entity = self.session.query(Server).get(server_id)
                for route_json in resp.msg['route_list']:
                    route_json = convert(route_json)
                    if route_json.destination_id != self.server.id \
                            and route_json.proxy_server_id != self.server.id \
                            and route_json.gate_id not in [g.id for g in self.server.gates]:
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
                self.logger.error(f"Error while connecting with {s}. Error: {resp}")

        # Select new routes based on neighbour routes
        neighbour_ids = [s.id for s in Server.get_neighbours(session=self.session)]
        for destination_id in filter(lambda s: s not in neighbour_ids, temp_table_routes.keys()):
            route = self.session.query(Route).filter_by(destination_id=destination_id).one_or_none()
            if not route:
                server = self.session.query(Server).get(destination_id)
                if not server:
                    continue
                else:
                    route = Route(destination=server)
            temp_table_routes[destination_id].sort(key=lambda x: x.cost or MAX_COST)
            if len(temp_table_routes[destination_id]) > 0:
                min_route = temp_table_routes[destination_id][0]
                proxy_server: Server = self.session.query(Server).get(min_route.proxy_server)
                cost = min_route.cost
                if route.proxy_server != proxy_server or route.cost != cost:
                    rc = RouteContainer(proxy_server, None, cost)
                    route.set_route(rc)
                    changed_routes[route.destination] = rc
                    self.session.add(route)

        data = {}
        for server, temp_route in changed_routes.items():
            data.update({str(server): {'proxy_server': str(temp_route.proxy_server), 'gate': str(temp_route.gate),
                                       'cost': str(temp_route.cost)}})
        return changed_routes

    async def _async_refresh_route_table(self, discover_new_neighbours=False, check_current_neighbours=False,
                                         max_num_discovery=None) -> t.Dict[Server, RouteContainer]:
        """Gets route tables of all neighbours and updates its own table based on jump weights.
        Needs a Flask App Context to run.

        Parameters
        ----------
        discover_new_neighbours:
            tries to discover new neighbours
        check_current_neighbours:
            checks if current neighbours are still neighbours
        max_num_discovery:
            maximum number of possible nodes to check as neighbour

        Returns
        -------
        None
        """

        self.logger.debug('Refresh Route Table')
        neighbours = Server.get_neighbours(session=self.session)
        not_neighbours = Server.get_not_neighbours(session=self.session)

        changed_routes: t.Dict[Server, RouteContainer] = {}

        not_neighbours_anymore = []
        new_neighbours = []

        aws = []
        if check_current_neighbours:
            if neighbours:
                self.logger.debug(f"Checking current neighbours: " + ', '.join([str(s) for s in neighbours]))
                aws.append(_async_set_current_neighbours(neighbours, changed_routes))
            else:
                self.logger.debug(f"No neighbour to check")

        if discover_new_neighbours:
            if not_neighbours[:max_num_discovery]:
                rs = list(not_neighbours)
                random.shuffle(rs)
                target = rs[:max_num_discovery]
                target.sort(key=lambda s: s.name)
                self.logger.debug(
                    f"Checking new neighbours{f' (limited to {max_num_discovery})' if max_num_discovery else ''}: "
                    + ', '.join([str(s) for s in target]))
                aws.append(_async_discover_new_neighbours(target, changed_routes))
            else:
                self.logger.debug("No new neighbours to check")

        res = await asyncio.gather(*aws, return_exceptions=False)

        if check_current_neighbours and neighbours:
            not_neighbours_anymore = res.pop(0)
            if not_neighbours_anymore:
                self.logger.info(
                    f"Lost direct connection to the following nodes: " + ', '.join(
                        [str(s) for s in not_neighbours_anymore]))
        if discover_new_neighbours and not_neighbours[:max_num_discovery]:
            new_neighbours = res.pop(0)
            if new_neighbours:
                self.logger.info(f'New neighbours found: ' + ', '.join([str(s) for s in new_neighbours]))
            else:
                self.logger.debug("No new neighbours found")

        # remove routes whose proxy_server is a node that is not a neighbour
        query = self.session.query(Route).filter(
            Route.proxy_server_id.in_([s.id for s in list(set(not_neighbours).union(set(not_neighbours_anymore)))]))
        rc = RouteContainer(None, None, None)
        for route in query.all():
            route.set_route(rc)
            changed_routes[route.destination] = rc
        self.session.commit()

        # update neighbour lis

        neighbours = list(set(neighbours).union(set(new_neighbours)) - set(not_neighbours_anymore))

        if neighbours:
            self.logger.debug(f"Getting routing tables from {', '.join([str(s) for s in neighbours])}")
            responses = await asyncio.gather(
                *[ntwrk.async_get(server, 'api_1_0.routes', auth=get_root_auth()) for server in neighbours])

            cr = self._route_table_merge(dict(zip(neighbours, responses)))
            changed_routes.update(cr)

        return changed_routes

    def _update_route_table_from_data(self, new_routes: t.Dict, auth=None) -> t.Dict[Server, RouteContainer]:
        changed_routes = {}
        routes = new_routes.get('route_list', [])
        routes.sort(key=lambda x: x.get('cost') or MAX_COST, reverse=True)
        try:
            likely_proxy_server = self.session.query(Server).get(new_routes.get('server_id'))
            if not likely_proxy_server:
                self.logger.warning(f"Server id still '{new_routes.get('server_id')}' not created.")
                return changed_routes
            debug_new_routes = []
            for new_route in routes:
                target_server = self.session.query(Server).get(new_route.get('destination_id'))
                proxy_server = self.session.query(Server).get(new_route.get('proxy_server_id'))
                gate = self.session.query(Gate).get(new_route.get('gate_id'))
                dest_name = getattr(target_server, 'name', new_route.get('destination_id'))
                proxy_name = getattr(proxy_server, 'name', new_route.get('proxy_server_id'))
                gate_str = str(gate) if gate else new_route.get('gate_id')
                cost = new_route.get('cost')
                if gate_str and proxy_name:
                    gate_str = gate_str + '*' + proxy_name
                debug_new_routes.append(f'{dest_name} -> {gate_str or proxy_name} / {cost}')
                if target_server is None:
                    self.logger.warning(f"Destination server unknown {new_route.get('destination_id')}")
                    continue
                if target_server.id == self.server.id:
                    # check if server has detected me as a neighbour
                    if new_route.get('cost') == 0:
                        # check if I do not have it as a neighbour yet
                        if likely_proxy_server.route and likely_proxy_server.route.cost != 0:
                            # check if I have a gate to contact with it
                            route = check_gates(likely_proxy_server)
                            if isinstance(route, RouteContainer):
                                changed_routes[likely_proxy_server] = route
                                likely_proxy_server.set_route(route)
                else:
                    # server may be created without route (backward compatibility)
                    if target_server.route is None:
                        target_server.set_route(Route(destination=target_server))
                    # process routes whose proxy_server is not me
                    if self.server.id != new_route.get('proxy_server_id'):
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
                                        cost, time = ntwrk.ping(target_server, retries=1, timeout=20,
                                                                session=self.session)
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
                                                           json=dict(server_id=str(self.server.id),
                                                                     route_list=[target_server.route.to_json()]),
                                                           auth=get_root_auth(), timeout=5)
                                    if not resp.ok:
                                        self.logger.info(f'Unable to send route to {likely_proxy_server}: {resp}')
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

            query = self.session.query(Route).filter(
                Route.proxy_server_id.in_([s.id for s, r in changed_routes.items() if r.cost is None]))
            rc = RouteContainer(None, None, None)
            for route in query.all():
                route.set_route(rc)
                changed_routes[route.destination] = rc

            self.logger.debug(
                f"New routes processed from {likely_proxy_server.name}: {json.dumps(debug_new_routes, indent=2)}")
            # if changed_routes:
            #     Parameter.set('routing_last_refresh', get_now())
        except errors.InvalidRoute as e:
            debug_new_routes = []
            routes.sort(key=lambda x: x.get('cost') or MAX_COST, reverse=True)
            for new_route in routes:
                target_server = self.session.query(Server).get(new_route.get('destination_id'))
                proxy_server = self.session.query(Server).get(new_route.get('proxy_server_id'))
                gate = self.session.query(Gate).get(new_route.get('gate_id'))
                dest_name = getattr(target_server, 'name', new_route.get('destination_id'))
                proxy_name = getattr(proxy_server, 'name', new_route.get('proxy_server_id'))
                gate_str = str(gate) if gate else new_route.get('gate_id')
                cost = new_route.get('cost')
                if gate_str and proxy_name:
                    gate_str = gate_str + '*' + proxy_name
                debug_new_routes.append(f'{dest_name} -> {gate_str or proxy_name} / {cost}')
            self.logger.exception(
                "Error setting routes from following data: " + json.dumps(debug_new_routes, indent=4))
        return changed_routes

    def _new_node_in_cluster(self, server_id, routes):
        changed_routes = {}
        server = self.session.query(Server).get(server_id)

        # server might be sent cluster in message but not created in database
        if server:
            new_route = check_gates(server, timeout=5, retries=3, delay=2)
            if new_route and isinstance(new_route, RouteContainer):
                self.logger.debug(f'cluster IN: New neighbour {server} found through {new_route.gate}')
                server.set_route(new_route)
                changed_routes.update({server: new_route})
            else:
                self.logger.debug(f"cluster IN: {server} is not a neighbour")
            changed_routes.update(
                self._update_route_table_from_data({'server_id': server_id, 'route_list': routes}))

        return changed_routes

    def _remove_node_from_cluster(self, server_id):
        changed_routes = {}
        server = self.session.query(Server).get(server_id)

        if server:
            server.set_route(RouteContainer(None, None, None))
            lost_routes = self.session.query(Route).filter_by(proxy_server_id=server.id).options(
                orm.lazyload(Route.destination), orm.lazyload(Route.gate), orm.lazyload(Route.proxy_server)).count()
            if lost_routes:
                changed_routes = self._loop.run_until_complete(
                    self._async_refresh_route_table(discover_new_neighbours=False,
                                                        check_current_neighbours=False))

            changed_routes.update({server: RouteContainer(None, None, None)})

        return changed_routes

    async def _send_routes(self, exclude=None):

        servers = Server.get_neighbours(session=self.session)
        msg, debug_msg = self._format_routes_message(self._changed_routes)

        c_exclude = []
        if self.logger.level <= logging.DEBUG:
            if exclude:
                if is_iterable_not_string(exclude):
                    c_exclude = [self.session.query(Server).get(e) if not isinstance(e, Server) else e for e in exclude]
                else:
                    c_exclude = [
                        self.session.query(Server).get(exclude) if not isinstance(exclude, Server) else exclude]
                log_msg = f" (Excluded nodes: {', '.join([getattr(e, 'name', e) for e in c_exclude])}):"
            else:
                log_msg = ''

            if servers:
                log_msg = f"Sending route information to the following nodes: {', '.join([s.name for s in servers])} " \
                          f"{log_msg}{json.dumps(debug_msg, indent=2)}"
            else:
                log_msg = f"No servers to send new routing information:{log_msg}{json.dumps(debug_msg, indent=2)}"
                if debug_msg:
                    log_msg += '\n' + json.dumps(debug_msg, indent=2)

            if debug_msg and (servers or exclude):
                self.logger.debug(log_msg)

        exclude_ids = list(set([s.id for s in servers]).union([getattr(e, 'id', e) for e in c_exclude]))

        auth = get_root_auth()
        aw = [ntwrk.async_patch(s, view_or_url='api_1_0.routes',
                                json={'server_id': self.server.id, 'route_list': msg,
                                      'exclude': exclude_ids},
                                auth=auth) for s in servers]

        rs = await asyncio.gather(*aw, return_exceptions=True)

        for r, s in zip(rs, servers):
            if isinstance(r, Exception):
                self.logger.warning(
                    f"Error while trying to send route data to node {s}: "
                    f"{format_exception(r)}")
            elif not r.ok:
                if r.exception:
                    self.logger.warning(
                        f"Error while trying to send route data to node {s}: "
                        f"{format_exception(r.exception)}")
                else:
                    self.logger.warning(f"Error while trying to send route data to node {s}: {r}")
        self._changed_routes.clear()

    def _format_routes_message(self, routes: t.Dict[t.Union[Id, Server], RouteContainer] = None) -> t.Tuple[
        t.List, t.List]:
        if routes:
            iterator = routes.items()
        else:
            iterator = [(r.destination, r) for r in self.session.query(Route).all()]
        msg = []
        debug_msg = []
        for d, r in iterator:
            msg.append(
                dict(destination_id=getattr(d, 'id', d),
                     proxy_server_id=str(getattr(r.proxy_server, 'id')) if getattr(r.proxy_server, 'id',
                                                                                   None) else None,
                     gate_id=str(getattr(r.gate, 'id')) if getattr(r.gate, 'id', None) else None,
                     cost=r.cost))

            dest_name = getattr(d, 'name', d)
            proxy_name = getattr(r.proxy_server, 'name') if getattr(r.proxy_server, 'name',
                                                                    None) else None
            gate_str = str(r.gate) if r.gate else None
            cost = r.cost
            if gate_str and proxy_name:
                gate_str = gate_str + '*' + proxy_name
            debug_msg.append(f'{dest_name} -> {gate_str or proxy_name} / {cost}')

        return msg, debug_msg
