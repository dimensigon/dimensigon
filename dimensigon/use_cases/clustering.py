import datetime as dt
import json
import logging
import queue
import typing as t

from flask import current_app

from dimensigon.domain.entities import Server
from dimensigon.use_cases import routing
from dimensigon.use_cases.helpers import get_root_auth
from dimensigon.utils import asyncio
from dimensigon.utils.cluster import Cluster
from dimensigon.utils.helpers import format_exception
from dimensigon.utils.typos import Id
from dimensigon.web import network as ntwrk, threading

logger = logging.getLogger('dimensigon.cluster')


async def send_cluster_register(cr, servers=None, auth=None, exclude=None):
    if not servers:
        servers = Server.get_neighbours(exclude=exclude)
    responses = await ntwrk.parallel_requests(servers, 'post',
                                              view_or_url='api_1_0.cluster',
                                              json=cr,
                                              auth=auth or get_root_auth(),
                                              timeout=10)

    for r, s in zip(responses, servers):
        if not r.ok and logger.level <= logging.WARNING:
            logger.warning(
                f"Unable to send cluster information to {s}. Response: {r}")


def check_server_alive(server: Server):
    alive_server_ids = [i for i in current_app.cluster_manager.cluster if
                        server.id != i and i != Server.get_current().id]
    # check if I have it as a neighbour
    if server.route and server.route.cost == 0:
        route = routing.check_gates(server)
        if route:
            return True

    # in order to prevent broadcast to everyone, first try a ping
    cost, elapsed = ntwrk.ping(server, retries=1, timeout=15)
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
    alive_server_ids = current_app.cluster_manager.cluster.get_alive()
    updated = False
    for alive_server_id in alive_server_ids:
        if alive_server_id != Server.get_current().id:
            alive = check_server_alive(Server.query.get(Server))
            if not alive:
                current_app.cluster_manager.cluster.set_death(alive_server_id)
                updated = True
    return updated


async def check_heartbeat_and_send(cluster_session_id: int, heartbeat_id: dt.datetime,
                                   exclude: t.Optional[t.List[Id]] = None):
    cr = current_app.cluster_manager.cluster.set_alive(cluster_session_id, heartbeat_id)
    if cr:
        await send_cluster_register(cr, exclude=exclude)


class ClusterManager:

    def __init__(self, app, maxsize=None, threshold=None, retain_time=2, start=True):
        self.app = app
        self.queue = queue.Queue(maxsize=maxsize or 10000)
        self.cluster = Cluster(threshold=threshold)
        self._stop = False
        self.buffer: t.Dict[Id, t.Dict] = {}
        self.retain_time = retain_time
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.run, name='cluster_manager')
        self._change_buffer_lock = threading.RLock()
        self._timer = None
        if start:
            self._thread.start()

    @property
    def running(self):
        return not self._stop

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

    def set_alive(self, ident, alive=None):
        cr = self.cluster.set_alive(ident, alive)
        if cr:
            with self._change_buffer_lock:
                self._add2buffer(cr)

    def set_death(self, ident, death=None):
        cr = self.cluster.set_death(ident, death)
        if cr:
            with self._change_buffer_lock:
                self._add2buffer(cr)

    def set_keepalive(self, ident: Id, keepalive=None):
        cr = self.cluster.set_keepalive(ident, keepalive)
        if cr:
            with self._change_buffer_lock:
                self._add2buffer(cr)

    def put(self, data: t.Union[t.Dict, t.List[t.Dict]], block=True, timeout=None):
        self.queue.put(data, block=block, timeout=timeout)

    def send_data(self):
        with self.app.app_context():
            # time to send data
            neighbours = Server.get_neighbours()
            if neighbours:
                auth = get_root_auth()
                with self._change_buffer_lock:
                    temp_buffer = dict(self.buffer)
                    self.buffer.clear()

                logger.debug(
                    f"Sending cluster information to the following nodes {', '.join([s.name for s in neighbours])}: "
                    f"{json.dumps(log_data(temp_buffer.values()), indent=2)}")
                try:
                    responses = self.loop.run_until_complete(
                        ntwrk.parallel_requests(neighbours, 'POST', view_or_url='api_1_0.cluster',
                                                json=list(temp_buffer.values()), auth=auth))
                except Exception as e:
                    logger.error(f"Unable to send cluster information to neighbours: "
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

                # check if new data arrived during timer execution
                with self._change_buffer_lock:
                    if self.buffer:
                        self._timer = threading.Timer(interval=1, function=self.send_data)
                        self._timer.start()
                    else:
                        self._timer = None
            else:
                logger.debug(f"No neighbour servers to send cluster information")
                with self._change_buffer_lock:
                    self._timer = None

    def run(self):
        logger.debug('Starting cluster manager')
        while not self._stop:
            try:
                item = self.queue.get(block=True, timeout=5)
            except queue.Empty:
                pass
            else:
                if item == 'STOP':
                    break
                elif item:
                    changed_ids = self.cluster.update_cluster(item)
                    for c_id in changed_ids:
                        self._add2buffer(self.cluster.get(c_id))
        logger.debug('Stopping cluster manager')


def log_data(data):
    debug_data = []
    for cr in data:
        cr = dict(cr)
        cr['name'] = getattr(Server.query.get(cr['id']), 'name', cr['id'])
        debug_data.append(cr)
    return debug_data
