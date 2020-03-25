import base64
import concurrent
import json
import os
import threading
import time
import typing as t
import uuid
from collections import ChainMap
from concurrent.futures.thread import ThreadPoolExecutor

import aiohttp
from flask import current_app
from flask_jwt_extended import create_access_token, get_jwt_identity

import dm.use_cases.deployment as dpl
import dm.use_cases.exceptions as ue
from dm import defaults
from dm.domain.entities import *
from dm.domain.entities import bypass_datamark_update
from dm.domain.entities.locker import Scope
from dm.domain.locker_memory import PriorityLocker
from dm.network.low_level import check_host
from dm.use_cases.base import OperationFactory
from dm.use_cases.lock import lock_scope
from dm.use_cases.mediator import Mediator
from dm.utils import asyncio
from dm.utils.decorators import logged
from dm.utils.helpers import get_distributed_entities, convert
from dm.utils.typos import Id
from dm.web import db
from dm.web.network import ping, get, HTTPBearerAuth, async_post, async_patch


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
        self._mediator = Mediator(interactor=self)
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
            else:
                current_app.logger.error(f"Unable to get a valid response from server {server}: {resp[1]}")
            upgrade_catalog(delta_catalog)


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
    me = Server.get_current()
    if check_current_neighbours:
        for server in Server.get_neighbours():
            cost, time = ping(server, me, retries=1, timeout=1)
            if cost is None:
                server.route.gate = None
                server.route.proxy_server = None
                server.route.cost = None
                # try another gate
                for gate in server.gates:
                    if check_host(ip=gate.dns or gate.ip, port=gate.port, retry=2, delay=0.001, timeout=0.1):
                        server.route.gate = gate
                        server.route.proxy_server = None
                        server.route.cost = 0
                    break

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
            for gate in server.gates:
                if check_host(ip=gate.dns or gate.ip, port=gate.port, retry=2, delay=0.001, timeout=0.1):
                    server.route.gate = gate
                    server.route.proxy_server = None
                    server.route.cost = 0
                    break

    token = create_access_token(identity='root')
    pool_responses = []
    temp_table_routes: t.Dict[uuid.UUID, t.List[Route]] = {}
    neighoburs = Server.get_neighbours()
    for server in neighoburs:
        pool_responses.append(get(server, 'api_1_0.routes', auth=HTTPBearerAuth(token)))

    changed_routes = []
    for resp in pool_responses:
        if resp[1] == 200:
            msg = resp[0]

            likely_proxy_server_entity = Server.query.get(msg.get('server_id'))

            for route_json in msg['route_list']:
                route_json = convert(route_json)
                # noinspection PyTypeChecker
                route_json.destination = uuid.UUID(route_json.destination_id)
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
                        temp_table_routes[route_json.destination_id].append(route_json)
                    elif route_json.cost is None:
                        # remove a routing if gateway cannot reach the destination
                        temp_table_routes[route_json.destination_id].append(route_json)
        else:
            s = neighoburs[pool_responses.index(resp)]
            current_app.logger.error(f"Error while connecting with {s}. Error: {resp[1]}, {resp[0]}")

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
            proxy_server = Server.query.get(min_route['proxy_server_id'])
            cost = min_route['cost']
            if route.proxy_server != proxy_server or route.cost != cost:
                route.proxy_server = proxy_server
                route.cost = cost
                changed_routes.append(route.to_json())
                break

    return changed_routes


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
