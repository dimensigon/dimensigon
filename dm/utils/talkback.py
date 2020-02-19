import functools
import itertools
import threading
import typing as t

EVENT_EXISTS_ITEM = 2 ** 0
EVENT_UPDATE_ITEM = 2 ** 1


class Event(list):
    def __call__(self, *args, **kwargs):
        for item in self:
            item(*args, **kwargs)


_KT = t.TypeVar('_KT')  # Key type.
_VT = t.TypeVar('_VT')  # Value type.


class Talkback(dict):

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._listeners = Event()

    def __setitem__(self, key, value):
        with self._lock:
            self._listeners(key)
            print(f"{key}: {value}")
        super(Talkback, self).__setitem__(key, value)

    def update(self, __m: t.Mapping[_KT, _VT] = None, **kwargs: _VT) -> None:
        with self._lock:
            if isinstance(__m, t.Dict):
                it = __m.items()
            else:
                it = __m or []
            for k, v in itertools.chain(it, kwargs.items()):
                self._listeners(k)
        super().update(__m or {}, **kwargs)

    def _wait_event(self, flag, expected_key, key):
        if expected_key == key:
            flag.set()
            func = None
            for func in self._listeners:
                if flag in func.args:
                    break
            if func:
                self._listeners.remove(func)

    def wait(self, key, event_mask, timeout=None):
        with self._lock:
            if event_mask & EVENT_EXISTS_ITEM:
                if key not in self:
                    flag = threading.Event()
                    func = functools.partial(self._wait_event, flag, key)
                    self._listeners.append(func)
                else:
                    return True
            elif event_mask & EVENT_UPDATE_ITEM:
                flag = threading.Event()
                func = functools.partial(self._wait_event, flag, key)
                self._listeners.append(func)
        r = flag.wait(timeout)
        if not r:
            self._listeners.remove(func)
        return r

    def wait_exists(self, key, timeout=None):
        return self.wait(key, EVENT_EXISTS_ITEM, timeout)

    def wait_update(self, key, timeout=None):
        return self.wait(key, EVENT_UPDATE_ITEM, timeout)
