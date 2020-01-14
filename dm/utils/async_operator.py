import heapq
import inspect
import itertools
import threading
import time
import typing as t
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial

from flask import Flask

from dm.utils.typos import Id, Ids


@dataclass
class CompletedProcess:
    """
    Data class to save the return value of the async op.

    returndata:
        return data passed through return from the async op.
    runtime:
        time in seconds taken to complete the function.
    excep:
        exception raised. None if no exception raised
    """
    returndata: t.Any
    runtime: float = None
    excep: t.Optional[Exception] = None


class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()


class Full(Exception):
    pass


class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    FINISHED = auto()
    ERROR = auto()


class AsyncTask(threading.Thread):
    """
    executes the async process
    """

    def __init__(self, id_: Id, async_proc: t.Callable, async_proc_args: t.Tuple = None,
                 async_proc_kw: t.Dict[str, t.Any] = None,
                 callback: t.Callable[[], None] = None, callback_args: t.Tuple = None,
                 callback_kw: t.Dict[str, t.Any] = None,
                 name_: str = None,
                 set_progress: t.Callable = None, app: Flask = None):
        super().__init__(name=name_ or str(async_proc).replace('<', '').replace('>', ''))
        self._id = id_
        self.async_proc = async_proc
        self.async_proc_args = async_proc_args or tuple()
        self.async_proc_kw = async_proc_kw or dict()
        self.callback = callback
        self.callback_args = callback_args or tuple()
        self.callback_kw = callback_kw or dict()
        self._e = None
        self._data = None
        self._set_progress_func = set_progress
        self.app = app
        self.daemon = True
        self.running = threading.Event()

    @property
    def e(self):
        return self._e

    @property
    def status(self) -> TaskStatus:
        status = TaskStatus.PENDING
        if self.is_alive():
            status = TaskStatus.RUNNING
        elif self.running.is_set():
            status = TaskStatus.FINISHED
            if self._e:
                status = TaskStatus.ERROR
        return status

    @property
    def id(self):
        return self._id

    def run(self):
        self.running.set()
        async_params = inspect.signature(self.async_proc).parameters

        start_time = time.time()

        if self.app:
            self.app.app_context().push()
        try:
            try:
                # check if function gets parameter progress_indicator
                if 'set_progress' in async_params and self._set_progress_func:
                    self._data = self.async_proc(*self.async_proc_args, set_progress=self._set_progress_func,
                                                 **self.async_proc_kw)
                else:
                    self._data = self.async_proc(*self.async_proc_args, **self.async_proc_kw)
            except Exception as e:
                self._e = e
            delta = time.time() - start_time

            cp = CompletedProcess(returndata=self._data, excep=self._e, runtime=delta)

            if self.callback:
                if 'data' in inspect.signature(self.callback).parameters:
                    self.callback(*self.callback_args, data=cp, **self.callback_kw)
                else:
                    self.callback(*self.callback_args, **self.callback_kw)
        finally:
            if self.app:
                self.app.app_context().pop()

    def __eq__(self, other):
        return self.id == other.id

    def __lt__(self, other):
        return self.id < other.id

    def __hash__(self):
        return id(self)


class AsyncOperator(StoppableThread):
    """
    Thread that executes async calls and executes the callback once the async call finishes
    """

    # __metaclass__ = Singleton

    def __init__(self, max_threads: int = 5, wait_interval: float = 0.005, priority: bool = True,
                 initial_count: int = 1, maxsize_pending: int = None, start=True):
        """
        Parameters
        ----------
        max_threads
            max threads that will run in parallel to process async process
        wait_interval
            interval for checking the async process queue to see if it must launch an async process
        priority
            sets if the queue will be a FIFO queue or a Priority queue
        initial_count
            initial id number.
        maxsize_pending
            sets the maximum async process that will be waiting. If full, the register process will through a Full exception
        """
        super().__init__(name='AsyncOperator')
        self.max_threads = max_threads
        self.wait_interval = wait_interval
        self.maxsize_pending = maxsize_pending
        self.__lock = threading.Lock()
        self._counter = itertools.count(initial_count)
        self._entry_finder: t.Dict[int, t.List[t.Union[int, AsyncTask, int]]] = {}

        self.__pending_tasks: t.List[AsyncTask] = []
        self.priority = priority
        self.daemon = True
        if start:
            self.start()

    def tasks_in_state(self, *args) -> t.List[int]:
        return [entry[1].id for entry in self._entry_finder.values() if entry[1].status in args]

    def num_tasks_in_state(self, *args) -> int:
        if not args:
            return len(self._entry_finder)
        else:
            return sum(1 for entry in self._entry_finder.values() if entry[1].status in args)

    def run(self):
        """
        Runs the main

        Returns
        -------
        None
        """
        while not self.stopped():
            # check whether there are async tasks to execute
            if self.num_tasks_in_state(TaskStatus.RUNNING) < self.max_threads:
                try:
                    self.__lock.acquire()
                    entry = heapq.heappop(self.__pending_tasks)
                except IndexError:
                    self.__lock.release()
                    self._stop_event.wait(timeout=self.wait_interval)
                else:
                    entry[1].start()
                    self.__lock.release()
            else:
                self._stop_event.wait(timeout=self.wait_interval)

    def purge(self):
        """
        Deletes finished tasks in the entry_finder

        Returns
        -------
        None
        """
        for task_id in self.tasks_in_state(TaskStatus.FINISHED, TaskStatus.ERROR):
            del self._entry_finder[task_id]

    def wait_tasks(self, ids: Ids = None, timeout: float = None):
        """
        waits the tasks passed by parameter to finish their execution

        Parameters
        ----------
        ids
            iterable with ids to wait or id to wait. If None it will wait for all tasks pending and running
        timeout
            total timeout waiting for all tasks to finish.

        Returns
        -------
        bool
            returns True if all tasks passed by parameter finished. Otherwise, returns False
        """
        if not self.is_alive():
            raise RuntimeError('AsyncOperator thread must start before call on wait_tasks')
        if type(ids) is int:
            ids_ = [ids]
        elif ids is None:
            ids_ = (task_id for task_id in self.tasks_in_state(TaskStatus.PENDING, TaskStatus.RUNNING))
        else:
            ids_ = ids
        start_time = time.time()
        for id_ in ids_:
            try:
                priority, task, progress = self._entry_finder[id_]
            except KeyError:
                continue
            remainder = max((timeout - (time.time() - start_time)), 0) if timeout is not None else None
            res = task.running.wait(timeout=remainder)
            if res:
                remainder = max((timeout - (time.time() - start_time)), 0) if timeout is not None else None
                task.join(timeout=remainder)
                if task.is_alive():
                    return False
            else:
                return False
        return True

    def progress(self, ids: Ids) -> t.List[int]:
        """
        Checks the task's progress
        Parameters
        ----------
        ids
            ids from which to retrieve progress status

        Returns
        -------
        t.List[int]
            returns a list with the progress of each task. Same order as input parameter ids
        """
        if type(ids) is int:
            ids_ = [ids]
        else:
            ids_ = ids

        res = [self._entry_finder[id_][2] for id_ in ids_]
        return res[0] if type(ids) is int else res

    def status(self, ids: Ids) -> t.List[TaskStatus]:
        """
        Checks the task's status

        Parameters
        ----------
        ids
            ids from which to retrieve progress status

        Returns
        -------
        t.List[TaskStatus]
            returns a list with the status of each task. Same order as input parameter ids
        """
        if type(ids) is int:
            ids_ = [ids]
        else:
            ids_ = ids

        res = []
        for id_ in ids_:
            res.append(self._entry_finder[id_][1].status)
        return res[0] if type(ids) is int else res

    def exception(self, id_: Id):
        return self._entry_finder[id_][1].e

    @property
    def done(self) -> bool:
        """
        checks if all task are done

        Returns
        -------
        bool:
            True if all tasks are done. False otherwise
        """
        self.__lock.acquire()
        cond = len(self.__pending_tasks) == 0 and self.num_tasks_in_state(TaskStatus.RUNNING) == 0
        self.__lock.release()
        return cond

    def register(self, async_proc: t.Callable, async_proc_args: t.Tuple = None,
                 async_proc_kw: t.Dict[str, t.Any] = None,
                 callback: t.Callable[[], None] = None, callback_args: t.Tuple = None,
                 callback_kw: t.Dict[str, t.Any] = None,
                 priority: int = 100,
                 name: str = None, app: Flask = None):

        """
        Registers an async process to be executed

        Parameters
        ----------
        async_proc:
            function call to be executed and its arguments.
        async_proc_args
            arguments to be passed to the async_proc function
        async_proc_kw
            keyword arguments to be passed to the async_proc function
        callback:
            function to execute once the async process finishes its execution.
            A data parameter will be passed to the callback if set. "data" arg will be a CompletedProcess object.
            For more information check docstrings from CompletedProcess.
            callback(*args, data=CompletedProcess, **kwargs)
        callback_args
            arguments to be passed to the callback function
        callback_kw
            keyword arguments to be passed to the callback function
        priority:
            sets the priority in case the queue is a Priority Queue. The lowest valued entries are retrieved first
        name:
            name of the task. The thread will have the task name as thread.name

        Notes
        -----
        async_op could have explicit parameter set_progress which is a function can be colled inside async_op to set
            the task progress. It goes from 0 to 100.

        Returns
        -------
        int
            task's id. Used to reference back to the task, wait for the task to finish, get progress, and so on.

        Raises
        ------
        Full
            When maxsize_pending is set and the size of pending_tasks reaches maxsize_pending
        """

        def set_(progress: int, entry_: [int, AsyncTask, int, TaskStatus]) -> None:
            assert 0 <= progress <= 100
            entry_[2] = progress

        if self.maxsize_pending:
            if len(self.__pending_tasks) >= self.maxsize_pending:
                raise Full('Pending tasks reached its maximum size')
        count = next(self._counter)

        if not self.priority:
            priority = 1

        entry = [priority, None, 0]
        task = AsyncTask(id_=count, async_proc=async_proc, async_proc_args=async_proc_args, async_proc_kw=async_proc_kw,
                         callback=callback, callback_args=callback_args, callback_kw=callback_kw,
                         name_=name, set_progress=partial(set_, entry_=entry))
        entry[1] = task

        self.__lock.acquire()
        self._entry_finder[task.id] = entry
        heapq.heappush(self.__pending_tasks, entry)
        self.__lock.release()
        return count

    def stop(self):
        super().stop()
        self.purge()
