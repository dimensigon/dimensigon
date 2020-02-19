import base64
import concurrent
import os
import threading
import time
import typing as t
import uuid
from collections import ChainMap
from concurrent.futures.thread import ThreadPoolExecutor

import aiohttp
import requests
import rsa
import six
from flask import current_app, g
from flask_jwt_extended import create_access_token
from returns.pipeline import is_successful
from returns.result import Result
from returns.result import safe

import dm.use_cases.deployment as dpl
import dm.use_cases.exceptions as ue
from dm import db
from dm.domain.entities import *
from dm.domain.exceptions import StateAlreadyInUnlock
from dm.domain.locker import PriorityLocker
from dm.network.gateway import unpack_msg, ping, pack_msg
from dm.use_cases.base import OperationFactory, Scope
from dm.use_cases.exceptions import ServersMustNotBeBlank, ErrorLock
from dm.use_cases.helpers import get_servers_from_scope
from dm.use_cases.mediator import Mediator
from dm.utils.decorators import logged
from dm.utils.helpers import get_distributed_entities, convert

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


DEFAULT_CHUNK_SIZE = 20971520  # 20 MB
DEFAULT_MAX_SENDERS = 4


def _send_chunk(url: str, transfer_id: str, chunk: int, chunk_size: int, file: str, cipher_key: bytes,
                priv_key: rsa.PrivateKey,
                session: requests.Session, dest_id: str):
    json_msg = {}
    json_msg.update(transfer_id=transfer_id)
    json_msg.update(chunk=chunk)

    with open(file, 'rb') as fd:
        fd.seek(chunk * chunk_size)
        chunk_content = fd.read(chunk_size)
    json_msg.update(content=chunk_content)

    packed_msg = pack_msg(data=json_msg, cipher_key=cipher_key, priv_key=priv_key)
    return session.post(url, json=packed_msg, headers={'D-Destination': dest_id})


def send_software(software: t.Union[SoftwareServerAssociation, uuid.UUID],
                  dest_server: t.Union[Server, uuid.UUID],
                  dest_path: str,
                  talkback: t.Callable[..., None] = None,
                  chunk_size: int = DEFAULT_CHUNK_SIZE,
                  max_senders: int = DEFAULT_MAX_SENDERS) \
        -> t.Optional[t.List[t.Tuple[int, t.Union[Exception, requests.Response]]]]:
    talkback = talkback or dict
    talkback(progress=0)

    if isinstance(software, (six.string_types, uuid.UUID)):
        soft = Software.query.get(software)
        if not software:
            raise ValueError(f"Software id '{software}' not found")
        software = soft

    if isinstance(dest_server, (six.string_types, uuid.UUID)):
        ds = Server.query.get(dest_server)
        if not ds:
            raise ValueError(f"Server id '{dest_server}' not found")
        dest_server = ds

    chunks = software.size_bytes // chunk_size
    if software.size_bytes % chunk_size:
        chunks += 1

    dim = Dimension.get_current()
    # create transfer
    ssa = SoftwareServerAssociation.query.filter_by(software=software, server=dest_server)

    json_msg = dict(software_id=ssa.software, num_chunks=chunks, filename=os.path.basename(ssa.path),
                    dest_path=dest_path)
    msg = pack_msg(data=json_msg, pub_key=getattr(dim, 'public'), priv_key=getattr(dim, 'private'))
    cipher_key = base64.b64decode(msg.get('key', '').encode('ascii'))
    s = requests.Session()
    resp = s.post(dest_server.url('transfers'), msg, headers={'D-Destination': str(dest_server.id)})

    if resp.status_code == 202:
        json_resp = resp.json()
        data = unpack_msg(json_resp.get('transfer_id'), priv_key=getattr(dim, 'private'),
                          pub_key=getattr(dim, 'public'), cipher_key=cipher_key)
        transfer_id = data.get('transfer_id')
        talkback(progress=5, transfer_id=transfer_id)
        url = dest_server.url('transfer', transfer_id=transfer_id)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_senders) as executor:
            future_to_chunk = {executor.submit(_send_chunk, (
                url, transfer_id, chunk, chunk_size, ssa.path, cipher_key, g.dimension.private, s,
                str(dest_server.id))): chunk for chunk in range(1, chunks + 1)}
            retry_chunks = []
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    data = future.result()
                except Exception as exc:
                    retry_chunks.append(chunk)
                else:
                    if data.status_code != 200:
                        retry_chunks.append(chunk)
        if len(retry_chunks) == 0:
            talkback(progress=100)
        else:
            talkback(progress=50)
        if retry_chunks:
            url = dest_server.url('transfer', transfer_id=transfer_id)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_senders) as executor:
                future_to_chunk = {executor.submit(_send_chunk, (
                    url, transfer_id, chunk, chunk_size, ssa.path, cipher_key, g.dimension.private, s,
                    str(dest_server.id))): chunk for chunk in retry_chunks}
                error_chunks = []
                for future in concurrent.futures.as_completed(future_to_chunk):
                    chunk = future_to_chunk[future]
                    try:
                        data = future.result()
                    except Exception as exc:
                        error_chunks.append((chunk, exc))
                    else:
                        if data.status_code != 200:
                            error_chunks.append((chunk, data))
            if error_chunks:
                return error_chunks
            else:
                talkback(progress=100)
        else:
            return None
    else:
        raise RuntimeError(resp.content)
