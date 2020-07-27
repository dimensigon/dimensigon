import threading
import time
import typing as t
from collections import namedtuple

from dimensigon.utils.typos import Id


class Event(object):

    def __init__(self, id_, data):
        self._id = id_
        self.data = data

    @property
    def id(self):
        return self._id


_RegistryContainer = namedtuple('_RegistryContainer', ['func', 'args', 'kwargs', 'birth'])


class EventHandler(object):

    def __init__(self, discard_after=3600):
        self.discard_after = discard_after
        self._registry: t.Dict[Id, _RegistryContainer] = {}
        self._pending_events: t.Dict[Id, t.Tuple[Event, float]] = {}
        self._lock = threading.Lock()

    def discard(self):
        now = time.time()
        for k, c in dict(self._registry).items():
            if now - c.birth >= self.discard_after:
                self._registry.pop(k)
        for k, v in dict(self._pending_events).items():
            if now - v[1] >= self.discard_after:
                self._pending_events.pop(k)

    def register(self, key, func: t.Callable[..., None], args=None, kwargs=None):
        event = None
        with self._lock:
            if key not in self._registry and key not in self._pending_events:
                self._registry[key] = _RegistryContainer(func, args or (), kwargs or {}, time.time())
            elif key in self._pending_events:
                event, t = self._pending_events.pop(key)
            else:
                raise ValueError('event ID duplicated')
            self.discard()
        if event:
            func(event, *(args or ()), **(kwargs or {}))

    def dispatch(self, event: Event):
        func = None
        with self._lock:
            try:
                func, args, kwargs, birth = self._registry.pop(event.id)
            except KeyError:
                self._pending_events[event.id] = (event, time.time())
            self.discard()
        if func:
            func(event, *args, **kwargs)
