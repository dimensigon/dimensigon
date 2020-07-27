import threading
import threading
import typing as t
from abc import ABC

from typing_extensions import Protocol

from dimensigon.domain.exceptions import StateError, ApplicantError, StateAlreadyInPreventingLock, StateAlreadyInLock, \
    StateAlreadyInUnlock, StateTransitionError, PriorityError
from dimensigon.utils.typos import Priority

OE = t.Optional[t.Union[StateError, ApplicantError]]


class Comparable(Protocol):
    """type for objects that support < operator"""

    def __lt__(self, other) -> bool:
        ...


class State(ABC):

    def preventing_lock(self, lock: 'Locker') -> OE:
        return StateAlreadyInPreventingLock()

    def lock(self, lock: 'Locker') -> OE:
        return StateAlreadyInLock()

    def unlock(self, lock: 'Locker') -> OE:
        return StateAlreadyInUnlock()

    def __str__(self):
        return self.__class__.__name__


class UnlockState(State):

    def lock(self, lock: 'Locker') -> OE:
        return StateTransitionError('UNLOCK', 'LOCK')

    def preventing_lock(self, lock: 'Locker') -> OE:
        lock._state = PreventingLockState(lock.unlock, kwargs={'applicant': lock.applicant})
        return


class PreventingLockState(State):

    def __init__(self, func: t.Callable, args: t.Tuple = None, kwargs: t.Mapping[str, t.Any] = None):
        def safe_unlock(func_, *args_, **kwargs_):
            try:
                func_(*args_, **kwargs_)
            except StateError:
                pass

        args = args if args is not None else []
        kwargs = kwargs if kwargs is not None else {}
        self.timer = threading.Timer(interval=Locker.TIMEOUT, function=safe_unlock, args=(func, *args), kwargs=kwargs)
        self.timer.start()

    def lock(self, lock: 'Locker') -> OE:
        self.timer.cancel()
        lock._state = LockState()

    def unlock(self, lock: 'Locker') -> OE:
        self.timer.cancel()
        lock._state = UnlockState()


class LockState(State):

    def preventing_lock(self, lock: 'Locker') -> OE:
        return StateTransitionError('LOCK', 'PREVENTING_LOCK')

    def unlock(self, lock: 'Locker') -> OE:
        lock._state = UnlockState()
        return


# def uid_to_class(uid):
#     for name, cls in inspect.getmembers(sys.modules[__name__], lambda c: inspect.isclass(c) and issubclass(c, State)):
#         if getattr(cls, 'id', None) == uid:
#             return cls
#

class Locker:
    """
    class that holds the state of the lock
    """
    TIMEOUT: t.ClassVar = 90

    def __init__(self):
        self._state: State = UnlockState()
        self._applicant: t.Optional[Comparable] = None  # holds the owner identifier who requested the lock
        self._mutex = threading.Lock()

    def set_timeout(self, timeout: float):
        self.__class__.TIMEOUT = timeout
        return self

    @staticmethod
    def _raise_if_error(msg):
        if isinstance(msg, StateError):
            raise msg

    @property
    def state(self):
        return self._state

    @property
    def applicant(self) -> t.Optional[Comparable]:
        return self._applicant

    def preventing_lock(self, applicant: t.Any):
        with self._mutex:
            if self.applicant is not applicant and self.applicant is not None:
                raise ApplicantError()
            self._applicant = applicant
            msg = self._state.preventing_lock(self)
            self._raise_if_error(msg)

    def lock(self, applicant: t.Any):
        with self._mutex:
            if self.applicant is not applicant and self.applicant is not None:
                raise ApplicantError()
            msg = self._state.lock(self)
            self._raise_if_error(msg)

    def unlock(self, applicant: t.Any):
        with self._mutex:
            if self.applicant is not applicant and self.applicant is not None:
                raise ApplicantError()
            msg = self._state.unlock(self)
            self._raise_if_error(msg)
            self._reset_locker()

    def _reset_locker(self):
        self._applicant = None

    def stop_timer(self):
        if isinstance(self._state, PreventingLockState):
            self._state.timer.cancel()

    def __str__(self):
        return f'{self._state}'


class PriorityLocker:
    """
    Priority Locker class that prevents locking a locker if a more prior locker is trying to be locked

    """

    def __init__(self, priority: Comparable, persistent=False, uid=None):
        """

        Parameters
        ----------
        priority:
            locker priority. Could be any hashable instance that implements __lt__ method. 1 is higher priority than 2
        """
        self.priority = priority
        self._locker = Locker()

    def set_timeout(self, timeout: int):
        self._locker.set_timeout(timeout=timeout)

    @property
    def applicant(self):
        return self._locker.applicant

    @property
    def state(self):
        return self._locker.state

    def preventing_lock(self, lockers: t.Dict[Priority, 'PriorityLocker'], applicant: t.Any):
        # check if higher lockers are locked or in preventing lock
        cond = any(map(lambda s: isinstance(s, (PreventingLockState, LockState)),
                       [locker.state for priority, locker in lockers.items() if priority < self.priority]))
        if not cond:
            self._locker.preventing_lock(applicant=applicant)
        else:
            raise PriorityError()

    def lock(self, applicant: t.Any):
        self._locker.lock(applicant=applicant)

    def unlock(self, applicant: t.Any):
        self._locker.unlock(applicant=applicant)

    def stop_timer(self):
        self._locker.stop_timer()
