import abc
import datetime as dt
import json
import logging
import multiprocessing as mp
import queue
import random
import threading
import typing as t

from dataclasses import dataclass
from flask import current_app
from sqlalchemy.orm import sessionmaker

from dimensigon import defaults
from dimensigon.domain.entities import Server
from dimensigon.use_cases import routing
from dimensigon.use_cases.base import Process
from dimensigon.use_cases.helpers import get_root_auth
from dimensigon.utils import asyncio
from dimensigon.utils.helpers import format_exception, get_now
from dimensigon.utils.typos import Id
from dimensigon.web import network as ntwrk

if t.TYPE_CHECKING:
    from dimensigon.core import Dimensigon

_logger = logging.getLogger('dm.cluster')


async def send_cluster_register(cr, servers=None, auth=None, exclude=None):
    if not servers:
        servers = Server.get_neighbours(exclude=exclude)
    responses = await ntwrk.parallel_requests(servers, 'post',
                                              view_or_url='api_1_0.cluster',
                                              json=cr,
                                              auth=auth or get_root_auth(),
                                              timeout=10)

    for r, s in zip(responses, servers):
        if not r.ok and _logger.level <= logging.WARNING:
            _logger.warning(
                f"Unable to send cluster information to {s}. Response: {r}")


def check_server_alive(server: Server):
    alive_server_ids = [i for i in current_app.dm.cluster_manager.get_alive() if
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
    alive_server_ids = current_app.dm.cluster_manager.get_alive()
    updated = False
    for alive_server_id in alive_server_ids:
        if alive_server_id != Server.get_current().id:
            alive = check_server_alive(Server.query.get(Server))
            if not alive:
                current_app.dm.cluster_manager.put(ident=alive_server_id, keepalive=get_now(), death=True)
                updated = True
    return updated


async def check_heartbeat_and_send(cluster_session_id: int, heartbeat_id: dt.datetime,
                                   exclude: t.Optional[t.List[Id]] = None):
    cr = current_app.dm.cluster_manager.put(ident=cluster_session_id, keepalive=heartbeat_id)
    if cr:
        await send_cluster_register(cr, exclude=exclude)


class EventHook(list):

    def __iadd__(self, handler):
        if handler not in self:
            self.append(handler)
        return self

    def __isub__(self, handler):
        if handler in self:
            self.remove(handler)
        return self

    def __call__(self, *args, **kwargs):
        for handler in self:
            handler(*args, **kwargs)


class Event(abc.ABC):
    ident = None

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.ident == other.ident


class DeathEvent(Event):

    def __init__(self, ident):
        self.ident = ident


class NewEvent(Event):

    def __init__(self, ident):
        self.ident = ident


class KeepAliveEvent(Event):

    def __init__(self, ident, date):
        self.ident = ident
        self.date = date

    def __eq__(self, other):
        return super().__eq__(other) and self.date == other.date


class ZombieEvent(Event):

    def __init__(self, ident):
        self.ident = ident


class AliveEvent(Event):
    def __init__(self, ident):
        self.ident = ident


class EventDispatcher:

    def __init__(self):
        self._event = dict()
        for c in Event.__subclasses__():
            self._event[c.__name__] = EventHook()

    def listen(self, target: t.Type[Event], fn):
        self._event[target.__name__] += fn

    def remove(self, target: t.Type[Event], fn):
        self._event[target.__name__] -= fn

    def __call__(self, event: Event):
        self._event[event.__class__.__name__](event)


@dataclass
class _Entry:
    id: Id
    keepalive: dt.datetime = None
    death: bool = False
    zombie: bool = False


Input = t.Tuple[Id, dt.datetime, bool, bool]
Item = t.Union[Input, t.List[Input]]


class ClusterManager(Process):
    _logger = _logger

    def __init__(self, dimensigon: 'Dimensigon', maxsize=None, zombie_threshold=180, delayed=2):
        super().__init__(dimensigon.shutdown_event, name=self.__class__.__name__)
        self.dm = dimensigon
        self.Session = sessionmaker(bind=self.dm.engine)
        self.manager = mp.Manager()
        self.queue = mp.Queue(maxsize=maxsize or 10000)
        self._registry: t.Dict[Id, _Entry] = self.manager.dict()
        # self._registry: t.Dict[Id, _Entry] = dict()

        self._timer_registry: t.Dict[Id, threading.Timer] = dict()

        self.zombie_threshold = dt.timedelta(seconds=zombie_threshold)
        self._dispatcher = EventDispatcher()

        self._buffer: t.Dict[Id, _Entry] = {}  # data to be sent
        self.delayed_send_time = delayed  # delay in seconds between data change and sending data to other nodes
        self._lock = threading.Lock()  # lock used for consistency with Timer threads
        self._change_buffer_lock = threading.RLock()
        self._timer = None

    def _add2buffer(self, entry: _Entry):
        with self._change_buffer_lock:
            self._buffer.update({entry.id: entry})
            if self._timer is None:
                self._timer = threading.Timer(interval=self.delayed_send_time, function=self._send_data)
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
        with self._lock:
            item = _Entry(*item)
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
                        event = KeepAliveEvent(item.id, item.keepalive)
                    self._add2buffer(current)
            self._registry[item.id] = current
            self._dispatcher(event) if event else None

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

                _logger.log(1,
                            f"Sending cluster information to the following nodes {', '.join([s.name for s in neighbours])}"
                            )
                _logger.log(1, f"{json.dumps(log_data(temp_buffer.values()), indent=2)}")

                auth = get_root_auth()
                try:
                    responses = self._loop.run_until_complete(
                        ntwrk.parallel_requests(neighbours, 'POST', view_or_url='api_1_0.cluster',
                                                json=[{'id': e.id,
                                                       'keepalive': e.keepalive.strftime(defaults.DATEMARK_FORMAT),
                                                       'death': e.death} for e in
                                                      temp_buffer.values()], auth=auth, securizer=False))
                except Exception as e:
                    _logger.error(f"Unable to send cluster information to neighbours: "
                                  f"{format_exception(e)}")
                    # restore data with new data arrived
                    with self._change_buffer_lock:
                        temp_buffer.update(**self._buffer)
                        self._buffer.clear()
                        self._buffer.update(temp_buffer)
                else:
                    for s, r in zip(neighbours, responses):
                        if not r.ok:
                            _logger.warning(f"Unable to send data to {s}: {r}")

                # check if new data arrived during timer execution
                with self._change_buffer_lock:
                    if self._buffer:
                        self._timer = threading.Timer(interval=1, function=self._send_data)
                        self._timer.start()
                    else:
                        self._timer = None
            else:
                _logger.debug(f"No neighbour servers to send cluster information")
                with self._change_buffer_lock:
                    self._timer = None
        session.close()

    def _main(self):
        self._loop = asyncio.new_event_loop()
        while not self._stop.is_set():
            try:
                item = self.queue.get(timeout=0.05)
            except queue.Empty:
                continue
            else:
                self._process_item(item)

    def _shutdown(self):
        self.queue.close()
        self.queue.join_thread()
        self.manager.shutdown()
        for t in self._timer_registry.values():
            t.cancel()
        if self._timer:
            self._timer.cancel()
        self._loop.run_until_complete(self._loop.shutdown_asyncgens())
        self._loop.stop()
        self._loop.close()

    # public functions
    def put_many(self, data: t.List, block=True, timeout=None):
        self.queue.put(data, block, timeout)

    def put(self, ident: Id, keepalive: dt.datetime, death: bool = False, block=True, timeout=None):
        self.queue.put((ident, keepalive, death), block=block, timeout=timeout)

    def listen(self, target, fn):
        self._dispatcher.listen(target, fn)

    def remove(self, target, fn):
        self._dispatcher.remove(target, fn)

    def get_alive(self) -> t.List[Id]:
        return [e.id for e in self._registry.values() if not e.zombie and not e.death]

    def get_zombies(self) -> t.List[Id]:
        return [e.id for e in self._registry.values() if e.zombie and not e.death]

    def get_cluster(self, str_format=None):
        return [(e.id, e.keepalive if str_format is None else e.keepalive.strftime(str_format), e.death) for e in
                self._registry.values()]

    def __contains__(self, item):
        entity = self._registry.get(item, None)
        if not entity.zombie and not entity.death:
            return True
        else:
            return False

    def notify_cluster(self):
        from dimensigon.domain.entities import Server
        import dimensigon.web.network as ntwrk
        from dimensigon.use_cases.helpers import get_root_auth
        from dimensigon.use_cases import routing
        from dimensigon.domain.entities import Parameter

        with self.dm.flask_app.app_context():
            not_notify = set()
            me = Server.get_current()
            msg, debug_msg = routing.format_routes_message()

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
                        _logger.debug(f"Sending 'Cluster IN' message to {s}")
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
                            _logger.debug(f"Unable to send 'Cluster IN' message to {s} . Response: {resp}")
                    else:
                        _logger.debug(f"Skiping server {s} from sending 'Cluster IN' message")
                else:
                    self.put(me.id, now)
                # alive = [(getattr(Server.query.get(s_id), 'name', None) or s_id) for s_id in
                #          self.get_alive()]
                # _logger.info(f"Alive servers: {', '.join(alive)}")
            else:
                _logger.debug("No neighbour to send 'Cluster IN'")
                self.put(me.id, now)
