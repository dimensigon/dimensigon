import concurrent
import os
import random
import threading
import time
import typing as t
import uuid
from collections import ChainMap
from concurrent.futures.thread import ThreadPoolExecutor

import aiohttp
import requests

from flask import current_app, url_for, g
from flask_jwt_extended import create_access_token
from returns.pipeline import is_successful
from returns.result import Result
from returns.result import safe

import dm.use_cases.deployment as dpl
from dm.domain.entities.route import Route

from dm.domain.exceptions import StateAlreadyInUnlock
from dm.domain.locker import PriorityLocker
import dm.use_cases.exceptions as ue
from dm.network.gateway import unpack_msg, ping

from dm.use_cases.base import OperationFactory, Scope
from dm.use_cases.exceptions import ServersMustNotBeBlank, ErrorLock
from dm.use_cases.helpers import get_servers_from_scope
from dm.use_cases.mediator import Mediator
from dm.utils.async_operator import AsyncOperator
from dm.utils.decorators import logged
from dm.utils.helpers import get_distributed_entities, convert
from dm.web import db
from dm.domain.entities import Orchestration, Log, Server

if t.TYPE_CHECKING:
    from dm import Server
    from dm import Params


@logged
class Interactor:
    """
    border between user world and domain application world
    """

    def __init__(self):
        self.MAX_LINES = 1000
        self.op_factory = OperationFactory()
        self._lockers = {}
        for s in Scope:
            self._lockers.update({s: PriorityLocker(s)})
        self._mediator = Mediator(async_operator=AsyncOperator(), interactor=self)
        self._log_thread = None
        self._logs: t.List[Log] = []
        self._loop = None
        self._group = None
        self.is_running = threading.Event()  # event tells if send_data_log is running
        self._awake = threading.Event()
        self.max_workers = min(32, os.cpu_count() + 4)

    @property
    def server(self):
        return self._mediator.server

    @property
    def lockers(self):
        return self._lockers

    def stop_timer(self):
        """Stop the timer if it started"""
        for l in self._lockers.values():
            l.stop_timer()

    def _create_cmd_from_orchestration(self, orchestration: 'Orchestration', params: 'Params') -> dpl.CompositeCommand:
        def convert2cmd(d, mapping):
            nd = {}
            for k, v in d.items():
                nd.update({mapping[k]: [mapping[s] for s in v]})
            return nd

        undo_step_cmd_map = {s: dpl.UndoCommand(implementation=self.op_factory.create_operation(s),
                                                params=ChainMap(params, s.parameters),
                                                id_=s.id)
                             for s in orchestration.steps if s.undo}
        step_cmd_map = {}
        tree_step = {}

        for s in (s for s in orchestration.steps if not s.undo):
            tree_step.update({s: [s for s in orchestration.children[s] if not s.undo]})

            # create Undo CompositeCommand for every command
            cc_tree = convert2cmd(orchestration.subtree([s for s in orchestration.children[s] if s.undo]),
                                  undo_step_cmd_map)

            c = dpl.Command(self.op_factory.create_operation(s), undo_implementation=dpl.CompositeCommand(cc_tree),
                            params=ChainMap(params, s.parameters), id_=s.id)

            step_cmd_map.update({s: c})

        return dpl.CompositeCommand(convert2cmd(tree_step, step_cmd_map))

    # TODO implement safe function with the decorator @safe
    def deploy_orchestration(self, orchestration: 'Orchestration', params: 'Params'):
        """

        Parameters
        ----------
        orchestration
            orchestration to deploy
        params
            parameters to pass to the steps

        Returns
        -------
        t.Tuple[bool, bool, t.Dict[int, dpl.Execution]]:
            tuple with 3 values. (boolean indicating if invoke process ended up successfully,
            boolean indicating if undo process ended up successfully,
            dict with all the executions). If undo process not executed, boolean set to None
        """
        cc = self._create_cmd_from_orchestration(orchestration, params)

        res_do, res_undo = None, None
        res_do = cc.invoke()
        if not res_do:
            res_undo = cc.undo()

        return res_do, res_undo, cc.execution

    @safe
    def lock(self, scope: Scope, servers: t.List['Server'] = None) -> None:
        """
        locks the Locker if allowed
        Parameters
        ----------
        scope
            scope that lock will affect.
        servers
            if scope set to Scope.ORCHESTRATION,
        Returns
        -------
        Result
        """

        if scope.ORCHESTRATION == scope and servers is None:
            raise ServersMustNotBeBlank()

        servers = servers or get_servers_from_scope(scope)
        self._lockers[scope].preventing_lock(lockers=self._lockers, applicant=servers)
        try:
            self._mediator.lock_unlock('L', scope, servers=servers)
            self._lockers[scope].lock(applicant=servers)
        except ErrorLock as e:
            error_servers = [es.server for es in e]
            locked_servers = list(set(servers) - set(error_servers))
            self._mediator.lock_unlock('U', scope, servers=locked_servers)
            try:
                self._lockers[scope].unlock(applicant=servers)
            except StateAlreadyInUnlock:
                pass
            raise

    @safe
    def unlock(self, scope: Scope):
        """
        unlocks the Locker if allowed
        Parameters
        ----------
        scope

        Returns
        -------

        """
        servers = self._lockers[scope].applicant
        self._lockers[scope].unlock(applicant=servers)
        self._mediator.lock_unlock('U', scope, servers)

    @safe
    def upgrade_catalog(self, server):
        result = self.lock(Scope.UPGRADE, [server])
        if is_successful(result):
            delta_catalog = self._mediator.remote_get_delta_catalog(data_mark=self._catalog.max_data_mark,
                                                                    server=server)
            de = get_distributed_entities()
            inside = set([name for name, cls in de])

            outside = set(delta_catalog.keys())

            if len(inside ^ outside) > 0:
                raise ue.CatalogMismatch(inside ^ outside)

            for name, cls in de:
                if name in delta_catalog:
                    for dto in delta_catalog[name]:
                        o = cls(**dto)
                        db.session.add(o)

            result = self.unlock(Scope.UPGRADE)
            return result
        else:
            return result

    def _main_send_data_logs(self, delay, app=None):

        def send_data_log(log: 'Log'):
            data = ''.join(log.readlines())

            if data:
                try:
                    self._mediator.send_data_log(filename=log.dest_name or os.path.basename(log.file),
                                                 server=log.server,
                                                 data_log=data, dest_folder=log.dest_folder)
                except ue.CommunicationError as e:
                    server, response, code = e.args
                    if isinstance(response, dict):
                        response = response.get('error', response)
                    self.logger.error(
                        f"SendDataLog: Error while trying to communicate with server {str(server)}: {response}")
                else:
                    log.update_offset_file()

        self.is_running.set()
        self._awake.clear()
        while self.is_running.is_set():
            start = time.time()
            with app.app_context():
                self._logs = Log.query.all()

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers,
                                                       thread_name_prefix="send_log") as executor:
                future_to_log = {executor.submit(send_data_log, log): log for log in self._logs}

                for future in concurrent.futures.as_completed(future_to_log):
                    log = future_to_log[future]
                    try:
                        data = future.result()
                    except Exception:
                        self.logger.error(f"Error while trying to send data log {log}", exc_info=True)

            for _ in range(len(self._logs)):
                log = self._logs.pop()
                del log
            elapsed = time.time() - start
            self._awake.wait(None if delay is None else max(0 - elapsed, 0))

    def send_data_logs(self, blocking=True, delay=20):
        if not self.is_running.is_set() and self._log_thread is None and len(self._logs) == 0:
            if blocking:
                self._main_send_data_logs(delay, app=current_app._get_current_object())
            else:
                self._log_thread = threading.Thread(target=self._main_send_data_logs, args=(delay,),
                                                    kwargs=dict(app=current_app._get_current_object()),
                                                    name="SendDataLog")
                self._log_thread.start()
                self._log_thread.is_alive()

    def stop_send_data_logs(self):
        # abort thread
        self.is_running.clear()

        # awake thread if sleeping and wait until is stopped
        self._awake.set()

        if self._log_thread is not None:
            self._log_thread.join(120)
            if self._log_thread.is_alive():
                self.logger.error("Unable to stop Send Data Log Thread")
            else:
                self._log_thread = None

        # close all filehandlers pointing to the log files
        for _ in range(len(self._logs)):
            log = self._logs.pop()
            del log


def update_table_routing_cost(discover_new_neighbours=False, check_current_neighbours=False) -> t.List[Server]:
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
    if check_current_neighbours:
        for server in Server.get_neighbours():
            cost, time = ping(server)
            if cost is None:
                server.route.cost = None
                server.route.gateway = None
            # try:
            #     requests.get(server.url('root.healthcheck'), timeout=0.5,
            #                  verify=False)
            # except (requests.exceptions.ConnectTimeout, TimeoutError):
            #     # TODO: handle when a neighobur is not a neighbour anymore
            #     server.cost = None
            # else:
            #     server.cost = 0
            #     server.gateway = None

    if discover_new_neighbours:
        for server in Server.get_not_neighbours():
            try:
                requests.get(server.url('root.healthcheck'),
                             timeout=0.5,
                             verify=False)
            except (requests.exceptions.ConnectTimeout, TimeoutError):
                pass
            else:
                server.route.cost = 0
                server.route.gateway = None
    db.session.commit()
    token = create_access_token(identity='root')
    pool_responses = []
    temp_table_routes: t.Dict[uuid.UUID, t.List[Route]] = {}
    for server in Server.get_neighbours():
        pool_responses.append(
            requests.get(server.url('api_1_0.routes'),
                         headers={'Authorization': f'Bearer {token}'}, verify=False))

    changed_routes = []
    for resp in pool_responses:
        if (isinstance(resp, aiohttp.ClientResponse) and resp.status == 200) or (
                isinstance(resp, (requests.Response,)) and resp.status_code == 200):
            msg = unpack_msg(resp.json(), getattr(g.dimension, 'public', None),
                             getattr(g.dimension, 'private', None))
            resp.close()

            likely_gateway_server_entity = Server.query.get(msg.get('server_id'))

            for route_json in msg['route_list']:
                route_json = convert(route_json)
                # noinspection PyTypeChecker
                route_json.destination = uuid.UUID(route_json.destination)
                if route_json.gateway:
                    # noinspection PyTypeChecker
                    route_json.gateway = uuid.UUID(route_json.gateway)
                if route_json.destination != g.server.id and route_json.gateway != g.server.id:
                    if route_json.destination not in temp_table_routes:
                        temp_table_routes.update({route_json.destination: []})
                    if route_json.cost is not None:
                        route_json.cost += 1
                        route_json.gateway = likely_gateway_server_entity.id
                        temp_table_routes[route_json.destination].append(route_json)
                    elif route_json.cost is None:
                        # remove a routing if gateway cannot reach the destination
                        temp_table_routes[route_json.destination].append(route_json)

    # Select new routes based on neighbour routes
    MAX_COST = 9999999
    neighbour_ids = [s.id for s in Server.get_neighbours()]
    for destination_id in filter(lambda s: s not in neighbour_ids, temp_table_routes.keys()):
        route = Route.query.filter_by(destination_id=destination_id).one_or_none()
        if not route:
            # TODO: handle how to create new server. If through repository or through new routes
            continue
        temp_table_routes[destination_id].sort(key=lambda x: x.cost or MAX_COST)
        if len(temp_table_routes[destination_id]) > 0:
            min_route = temp_table_routes[destination_id][0]
            gateway = Server.query.get(min_route['gateway'])
            cost = min_route['cost']
            if route.gateway != gateway or route.cost != cost:
                route.gateway = gateway
                route.cost = cost
                changed_routes.append(route.to_json())
                break

    return changed_routes


def update_table_routing_static(discover_new_neighbours=False, check_current_neighbours=False):
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
    url_schema = current_app.config['PREFERRED_URL_SCHEME']
    # get all neighbours
    if check_current_neighbours:
        neighbours = []
        for server in Server.get_neighbours():
            try:
                requests.get(f"{url_schema}://{server.ip}:{server.port}{url_for('healthcheck')}", timeout=0.5,
                             verify=False)
            except requests.exceptions.ConnectTimeout:
                server.unreachable = True
            else:
                neighbours.append(server)
    else:
        neighbours = Server.get_neighbours()
    if discover_new_neighbours:
        for server in Server.get_not_neighbours():
            try:
                requests.get(f"{url_schema}://{server.ip}:{server.port}{url_for('healthcheck')}",
                             timeout=0.5,
                             verify=False)
            except requests.exceptions.ConnectTimeout:
                pass
            else:
                server.unreachable = False
                neighbours.append(server)
    token = create_access_token(identity='root')

    # loop = asyncio.get_event_loop()

    # async def get(url, tkn):
    #     async with ClientSession() as session:
    #         resp = await session.get(url,
    #                                  headers={'Authorization': f'Bearer {tkn}'},
    #                                  ssl=False,
    #                                  timeout=5)
    #         return resp

    tasks = []
    pool_responses = []
    table_routes: t.Dict[Server, t.List[t.List[uuid.UUID]]] = {}
    table_alt_routes: t.Dict[Server, t.List[t.List[uuid.UUID]]] = {}
    for server in neighbours:
        table_routes.update({server.id: [list()]})
        table_alt_routes.update({server.id: [list()]})
        pool_responses.append(
            requests.get(f"{url_schema}://{server.ip}:{server.port}{url_for('api_1_0.route', _external=False)}",
                         headers={'Authorization': f'Bearer {token}'}, verify=False))
    #     tasks.append(get(f"https://{server.ip}:{server.port}{url_for('api_1_0.route')}", token))
    # pool_responses = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=False))

    neighbour_ids = [n.id for n in neighbours]
    for r in pool_responses:
        if (isinstance(r, aiohttp.ClientResponse) and r.status == 200) or (
                isinstance(r, (requests.Response,)) and r.status_code == 200):
            msg = unpack_msg(r.json(), getattr(g.dimension, 'public', None),
                             getattr(g.dimension, 'private', None))
            r.close()

            jump_server_id = msg.get('server_id')

            for reachable_server_dict in msg['server_list']:
                rs_id = reachable_server_dict.get('id')
                if not (rs_id == g.server.id or rs_id in neighbour_ids):
                    if rs_id not in table_routes:
                        table_routes.update({rs_id: []})
                        table_alt_routes.update({rs_id: []})
                    table_routes[rs_id].append([jump_server_id] + reachable_server_dict.get('mesh_best_route', []))
                    table_alt_routes[rs_id].append([jump_server_id] + reachable_server_dict.get('mesh_alt_route', []))

    for server_id in table_routes.keys():
        server = Server.query.get(server_id)
        random.shuffle(table_routes[server_id])
        server.mesh_best_route = min(table_routes[server_id], key=len)
        table_routes[server_id].remove(server.mesh_best_route)
        table_alt_routes[server_id].extend(table_routes[server_id])
        random.shuffle(table_alt_routes[server_id])
        server.mesh_alt_route = min(table_alt_routes[server_id], key=len)
