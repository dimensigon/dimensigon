import typing as t

from dm.utils.typos import Id


class Event(object):

    def __init__(self, id_, data):
        self._id = id_
        self.data = data

    @property
    def id(self):
        return self._id


class EventHandler(object):

    def __init__(self):
        self._registry: t.Dict[Id, t.Tuple[t.Callable, t.Tuple, t.Dict[str, t.Any]]] = {}

    def register(self, key, func: t.Callable[..., None], args=None, kwargs=None):
        if key not in self._registry:
            self._registry[key] = (func, args or (), kwargs or {})
        else:
            raise ValueError('event ID duplicated')

    def dispatch(self, event: Event):
        try:
            func, args, kwargs = self._registry.pop(event.id)
        except KeyError:
            return False
        func(event, *args, **kwargs)
        return True
