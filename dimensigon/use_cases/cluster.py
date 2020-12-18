import datetime as dt
import json
import logging
import random
import threading
import typing as t

from dataclasses import dataclass
from sqlalchemy import orm
from sqlalchemy.orm import sessionmaker

from dimensigon import defaults
from dimensigon.domain.entities import Server, Route
from dimensigon.use_cases.mptools import Worker, MPQueue
from dimensigon.use_cases.mptools_events import BaseEvent
from dimensigon.use_cases.routing import InitialRouteSet
from dimensigon.utils import asyncio
from dimensigon.utils.helpers import format_exception, get_now
from dimensigon.utils.typos import Id
from dimensigon.web import network as ntwrk, get_root_auth

if t.TYPE_CHECKING:
    from dimensigon.core import Dimensigon


# self.logger = logging.getLogger('dm.cluster')


# async def send_cluster_register(cr, servers=None, auth=None, exclude=None):
#     if not servers:
#         servers = Server.get_neighbours(exclude=exclude)
#     responses = await ntwrk.parallel_requests(servers, 'post',
#                                               view_or_url='api_1_0.cluster',
#                                               json=cr,
#                                               auth=auth or get_root_auth(),
#                                               timeout=10)
# 
#     for r, s in zip(responses, servers):
#         if not r.ok and self.logger.level <= logging.WARNING:
#             self.logger.warning(
#                 f"Unable to send cluster information to {s}. Response: {r}")
# 
# 
# def check_server_alive(server: Server):
#     alive_server_ids = [i for i in current_app.dm.cluster_manager.get_alive() if
#                         server.id != i and i != Server.get_current().id]
#     # check if I have it as a neighbour
#     if server.route and server.route.cost == 0:
#         route = routing.check_gates(server)
#         if route:
#             return True
# 
#     # in order to prevent broadcast to everyone, first try a ping
#     cost, elapsed = ntwrk.ping(server, retries=1, timeout=15)
#     if cost is not None:
#         return True
#     responses = asyncio.run(ntwrk.parallel_requests(alive_server_ids, 'get',
#                                                     view_or_url='api_1_0.routes_neighbour',
#                                                     view_data=dict(server_id=server.id), timeout=10))
#     for r in responses:
#         if r.ok:
#             if r.msg.get('neighbour'):
#                 return True
#     return False


# def update_cluster_status():
#     alive_server_ids = current_app.dm.cluster_manager.get_alive()
#     updated = False
#     for alive_server_id in alive_server_ids:
#         if alive_server_id != Server.get_current().id:
#             alive = check_server_alive(Server.query.get(Server))
#             if not alive:
#                 current_app.dm.cluster_manager.put(ident=alive_server_id, keepalive=get_now(), death=True)
#                 updated = True
#     return updated
# 
# 
# async def check_heartbeat_and_send(cluster_session_id: int, heartbeat_id: dt.datetime,
#                                    exclude: t.Optional[t.List[Id]] = None):
#     cr = current_app.dm.cluster_manager.put(ident=cluster_session_id, keepalive=heartbeat_id)
#     if cr:
#         await send_cluster_register(cr, exclude=exclude)


class ClusterEvent(BaseEvent):
    """An Base class for Cluster related Event"""


class DeathEvent(ClusterEvent):
    """A node changed its state to DEATH"""


class NewEvent(ClusterEvent):
    """A node changed its state to NEW"""


class KeepAliveEvent(ClusterEvent):
    """A new KeepAlive Event has arrived"""


class ZombieEvent(ClusterEvent):
    """A node changed its state to ZOMBIE"""


class AliveEvent(ClusterEvent):
    """A node that was in ZOMBIE state changed its state to ALIVE"""


class NotifyClusterEnded(ClusterEvent):
    """Notify Cluster Process Ended"""


@dataclass
class _Entry:
    id: Id
    keepalive: dt.datetime = None
    death: bool = False
    zombie: bool = False

Input = t.Tuple[Id, dt.datetime, bool, bool]
Item = t.Union[Input, t.List[Input]]


class ClusterManager(Worker):
    ###########################
    # START Class Inheritance #
    def init_args(self, dimensigon: 'Dimensigon', maxsize=None, zombie_threshold=defaults.ZOMBIE_NODE,
                  send_interval=defaults.CLUSTER_SEND_PERIOD):
        self.dm = dimensigon
        self.Session = sessionmaker(bind=self.dm.engine)
        self.queue = MPQueue(maxsize=maxsize or 10000)
        self._registry: t.Dict[Id, _Entry] = self.dm.manager.dict()
        # self._registry: t.Dict[Id, _Entry] = dict()

        self._timer_registry: t.Dict[Id, threading.Timer] = dict()
        self.zombie_threshold = dt.timedelta(seconds=zombie_threshold)

        self._buffer: t.Dict[Id, _Entry] = {}  # data to be sent
        self.send_interval = send_interval  # delay in seconds between data change and sending data to other nodes
        self._lock = threading.Lock()  # lock used for consistency with Timer threads
        self._change_buffer_lock = threading.RLock()
        self._timer = None

    def startup(self):
        self._route_initiated = threading.Event()
        self.dispatcher.listen(InitialRouteSet, lambda x: self._route_initiated.set())
        self.dispatcher.listen('Listening', lambda x: self._notify_cluster_in())
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

    def shutdown(self):
        self._notify_cluster_out()
        self.queue.close()
        self.queue.join_thread()
        for t in self._timer_registry.values():
            t.cancel()
        if self._timer:
            self._timer.cancel()

    def main_func(self, *args, **kwargs):
        item = self.queue.safe_get()
        if item:
            self._process_item(item)

    # END Class Inheritance #
    #########################

    ############################
    # INIT Interface functions #
    def put_many(self, data: t.List, block=True, timeout=None):
        self.queue.put(data, block, timeout)

    def put(self, ident: Id, keepalive: dt.datetime, death: bool = False, block=True, timeout=None):
        self.queue.put((ident, keepalive, death), block=block, timeout=timeout)

    def get_alive(self) -> t.List[Id]:
        return [e.id for e in self._registry.values() if not e.zombie and not e.death] + [self.dm.server_id]

    def get_zombies(self) -> t.List[Id]:
        return [e.id for e in self._registry.values() if e.zombie and not e.death]

    def get_cluster(self, str_format=None):
        return [(e.id, e.keepalive if str_format is None else e.keepalive.strftime(str_format), e.death) for e in
                self._registry.values()] + [
            (self.dm.server_id, get_now() if str_format is None else get_now().strftime(str_format), False)]

    def __contains__(self, item):
        entity = self._registry.get(item, None)
        if item == self.dm.server_id or (entity and not (entity.zombie or entity.death)):
            return True
        else:
            return False

    # END Interface functions  #
    ############################

    ##############################
    # INNER methods & attributes #
    def _add2buffer(self, entry: _Entry):
        with self._change_buffer_lock:
            self._buffer.update({entry.id: entry})
            if self._timer is None:
                self._timer = threading.Timer(interval=self.send_interval, function=self._send_data)
                self._timer.start()

    def _cancel_timer(self, ident):
        if ident in self._timer_registry:
            self._timer_registry[ident].cancel()
            del self._timer_registry[ident]

    def _set_timer(self, ident, keepalive):
        self._cancel_timer(ident)
        th = self._timer_registry[ident] = threading.Timer(interval=self.zombie_threshold.seconds,
                                                           function=self.queue.put,
                                                           args=((ident, keepalive, None, True),),
                                                           kwargs=dict(block=True))
        th.start()

    def _process_one(self, item: Input):
        item = _Entry(*item)
        # discard item if it's me
        if item.id != self.dm.server_id:
            with self._lock:
                current = self._registry.get(item.id,
                                             _Entry(item.id, keepalive=dt.datetime(1, 1, 1, tzinfo=dt.timezone.utc),
                                                    death=True, zombie=False))
                event = None
                if item.zombie:
                    # zombie message
                    if current.keepalive == item.keepalive and not current.death:
                        current.zombie = True
                        event = ZombieEvent(item.id)
                elif item.death:
                    # death message
                    if not current.death or (current.death and item.keepalive > current.keepalive):
                        self._cancel_timer(current.id)
                        current.death = True
                        current.zombie = False
                        current.keepalive = item.keepalive

                        self._add2buffer(current)
                        event = DeathEvent(current.id)

                else:
                    if item.keepalive > current.keepalive:
                        # alive
                        current.keepalive = item.keepalive
                        # restart timer
                        self._set_timer(item.id, item.keepalive)
                        if current.death:
                            current.death = False
                            current.zombie = False
                            event = NewEvent(item.id)
                        elif current.zombie:
                            current.zombie = False
                            event = AliveEvent(item.id)
                        else:
                            pass
                            # event = KeepAliveEvent(item.id, item.keepalive)
                        self._add2buffer(current)
                self._registry[item.id] = current
                self.publish_q.safe_put(event) if event else None

    def _process_item(self, item: Item):
        if isinstance(item, list):
            [self._process_one(i) for i in item]
        else:
            self._process_one(item)

    def _send_data(self):
        session = self.Session()

        def log_data(data):
            debug_data = []
            for cr in data:
                server = dict(id=cr.id)
                name = getattr(session.query(Server).get(cr.id), 'name', cr.id)
                if name:
                    server.update(name=name)

                debug_data.append(
                    {'server': server, 'keepalive': cr.keepalive.strftime(defaults.DATEMARK_FORMAT), 'death': cr.death})
            return debug_data

        # time to send data
        with self.dm.flask_app.app_context():
            neighbours = Server.get_neighbours(session=session)
            if neighbours:
                with self._change_buffer_lock:
                    temp_buffer = dict(self._buffer)
                    self._buffer.clear()

                self.logger.debug(
                    f"Sending cluster information to the following nodes: {', '.join([s.name for s in neighbours])}"
                )
                self.logger.log(1, f"{json.dumps(log_data(temp_buffer.values()), indent=2)}")

                auth = get_root_auth()
                try:
                    responses = asyncio.run(
                        ntwrk.parallel_requests(neighbours, 'POST', view_or_url='api_1_0.cluster',
                                                json=[{'id': e.id,
                                                       'keepalive': e.keepalive.strftime(defaults.DATEMARK_FORMAT),
                                                       'death': e.death} for e in
                                                      temp_buffer.values()], auth=auth, securizer=False), )
                except Exception as e:
                    self.logger.error(f"Unable to send cluster information to neighbours: {format_exception(e)}")
                    # restore data with new data arrived
                    with self._change_buffer_lock:
                        temp_buffer.update(**self._buffer)
                        self._buffer.clear()
                        self._buffer.update(temp_buffer)
                else:
                    for r in responses:
                        if not r.ok:
                            self.logger.warning(f"Unable to send data to {r.server}: {r}")

                # check if new data arrived during timer execution
                with self._change_buffer_lock:
                    if self._buffer:
                        self._timer = threading.Timer(interval=1, function=self._send_data)
                        self._timer.start()
                    else:
                        self._timer = None
            else:
                self.logger.debug(f"No neighbour servers to send cluster information")
                with self._change_buffer_lock:
                    self._timer = None
        session.close()

    def _notify_cluster_in(self):
        from dimensigon.domain.entities import Server
        import dimensigon.web.network as ntwrk
        from dimensigon.domain.entities import Parameter

        try:
            signaled = self._route_initiated.wait(timeout=120)
        except Exception:
            return

        if not signaled:
            self.logger.warning("Route Event not fired.")

        self.logger.debug("Notify Cluster")
        with self.dm.flask_app.app_context():
            not_notify = set()
            me = Server.get_current()

            msg = [r.to_json() for r in Route.query.options(orm.lazyload(Route.destination), orm.lazyload(Route.gate),
                                                            orm.lazyload(Route.proxy_server)).all()]

            neighbours = Server.get_neighbours()

            if Parameter.get('join_server', None):
                join_server = Server.query.get(Parameter.get('join_server'))
            else:
                join_server = None

            now = get_now()
            msg = dict(keepalive=now.strftime(defaults.DATEMARK_FORMAT), routes=msg)
            if neighbours:
                random.shuffle(neighbours)
                first = [s for s in neighbours if s.id == Parameter.get('new_gates_server', None)]
                if first:
                    neighbours.pop(neighbours.index(first[0]))
                    neighbours = first + neighbours
                elif join_server in neighbours:
                    neighbours.pop(neighbours.index(join_server))
                    neighbours = [join_server] + neighbours
                for s in neighbours:
                    if s.id not in not_notify:
                        self.logger.debug(f"Sending 'Cluster IN' message to {s}")
                        resp = ntwrk.post(s, 'api_1_0.cluster_in', view_data=dict(server_id=str(me.id)),
                                          json=msg, timeout=10, auth=get_root_auth())
                        if resp.ok:
                            converted = []
                            for ident, str_keepalive, death in resp.msg['cluster']:
                                try:
                                    keepalive = dt.datetime.strptime(str_keepalive, defaults.DATEMARK_FORMAT)
                                except ValueError:
                                    continue
                                converted.append((ident, keepalive, death))
                            self.put_many(converted)
                            not_notify.update(resp.msg.get('neighbours', []))
                        else:
                            self.logger.debug(f"Unable to send 'Cluster IN' message to {s} . Response: {resp}")
                    else:
                        self.logger.debug(f"Skiping server {s} from sending 'Cluster IN' message")
                # alive = [(getattr(Server.query.get(s_id), 'name', None) or s_id) for s_id in
                #          self.get_alive()]
                # self.logger.info(f"Alive servers: {', '.join(alive)}")
            else:
                self.logger.debug("No neighbour to send 'Cluster IN'")
        self.logger.debug("Notify Cluster ended")

    def _notify_cluster_out(self):
        with self.dm.flask_app.app_context():
            servers = Server.get_neighbours()
            if servers:
                self.logger.debug(f"Sending shutdown to {', '.join([s.name for s in servers])}")
            else:
                self.logger.debug("No server to send shutdown information")
            if servers:
                responses = asyncio.run(
                    ntwrk.parallel_requests(servers, 'post',
                                            view_or_url='api_1_0.cluster_out',
                                            view_data=dict(server_id=str(Server.get_current().id)),
                                            json={'death': get_now().strftime(defaults.DATEMARK_FORMAT)},
                                            timeout=2, auth=get_root_auth()))
                if self.logger.level <= logging.DEBUG:
                    for r in responses:
                        if not r.ok:
                            self.logger.warning(f"Unable to send data to {r.server}: {r}")
