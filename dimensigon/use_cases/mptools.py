import abc
import functools
import inspect
import logging
import multiprocessing as mp
import multiprocessing.queues as mpq
import signal
import sys
import threading
import time
import typing as t
from queue import Empty, Full

from dimensigon.use_cases import mptools_events as events
from dimensigon.utils.helpers import is_iterable_not_string

DEFAULT_POLLING_TIMEOUT = 0.1
MAX_SLEEP_SECS = 0.1

_logger = logging.getLogger('dm.mptools')


class MPQueue(mpq.Queue):

    # -- See StackOverflow Article :
    #   https://stackoverflow.com/questions/39496554/cannot-subclass-multiprocessing-queue-in-python-3-5
    #
    # -- tldr; mp.Queue is a _method_ that returns an mpq.Queue object.  That object
    # requires a context for proper operation, so this __init__ does that work as well.
    def __init__(self, *args, **kwargs):
        ctx = mp.get_context()
        super().__init__(*args, **kwargs, ctx=ctx)

    def safe_get(self, timeout=DEFAULT_POLLING_TIMEOUT):
        try:
            if timeout is None:
                return self.get(block=False)
            else:
                return self.get(block=True, timeout=timeout)
        except Empty:
            return None

    def safe_put(self, item, timeout=DEFAULT_POLLING_TIMEOUT):
        try:
            self.put(item, block=True, timeout=timeout)
            return True
        except Full:
            return False

    def drain(self):
        item = self.safe_get()
        while item:
            yield item
            item = self.safe_get()

    def safe_close(self):
        num_left = sum(1 for __ in self.drain())
        self.close()
        self.join_thread()
        return num_left


# -- useful function
def _sleep_secs(max_sleep, end_time=999999999999999.9):
    # Calculate time left to sleep, no less than 0
    return max(0.0, min(end_time - time.time(), max_sleep))


# -- Signal Handling
class TerminateInterrupt(BaseException):
    pass


class SignalObject:
    MAX_TERMINATE_CALLED = 3

    def __init__(self, shutdown_event):
        self.terminate_called = 0
        self.shutdown_event = shutdown_event


def default_signal_handler(signal_object, exception_class, signal_num, current_stack_frame):
    signal_object.terminate_called += 1
    signal_object.shutdown_event.set()
    # if signal_object.loop:
    #     signal_object.loop.stop()
    _logger.info("shutdown event set")
    if signal_object.terminate_called >= signal_object.MAX_TERMINATE_CALLED:
        raise exception_class()


def init_signal(signal_num, signal_object, exception_class, handler):
    handler = functools.partial(handler, signal_object, exception_class)
    signal.signal(signal_num, handler)
    signal.siginterrupt(signal_num, False)


def init_signals(shutdown_event, int_handler, term_handler):
    signal_object = SignalObject(shutdown_event)
    init_signal(signal.SIGINT, signal_object, KeyboardInterrupt, int_handler)
    init_signal(signal.SIGTERM, signal_object, TerminateInterrupt, term_handler)
    return signal_object


class Observer(list):

    def __call__(self, event: events.EventMessage):
        for item in self:
            item(event)


EventType = t.Union[str, t.Type[events.EventMessage], events.EventMessage]


class EventHandler(threading.Thread):

    def __init__(self, queue: MPQueue, *args, **kwargs):
        super().__init__()
        self.queue = queue
        self.stop_event = threading.Event()
        self._event_handlers = {}

    @staticmethod
    def _e_type(event):
        if inspect.isclass(event) and issubclass(event, events.EventMessage):
            e_type = event.__name__
        elif isinstance(event, events.EventMessage):
            e_type = event.event_type
        else:
            e_type = event
        return e_type

    def listen(self, event_type: t.Union[t.Iterable[EventType], EventType],
               callback):
        if not is_iterable_not_string(event_type):
            event_type = [event_type]
        for et in event_type:
            sig = inspect.signature(callback)
            assert len(sig.parameters) == 1, "Callback must get 1 positional argument"
            e_type = self._e_type(et)

            if e_type not in self._event_handlers:
                self._event_handlers[e_type] = Observer()
            self._event_handlers[e_type].append(callback)

    def detach(self, event_type: t.Union[t.Iterable[EventType], EventType],
               callback):
        if not is_iterable_not_string(event_type):
            event_type = [event_type]
        for et in event_type:
            e_type = self._e_type(et)
            self._event_handlers.get(e_type, []).remove(callback)

    def run(self):
        while not self.stop_event.is_set():
            event = self.queue.safe_get()
            if event:
                # _logger.debug(f"Processing event {event}")
                e_type = self._e_type(event)
                if event in (events.StopEventHandler, events.Stop):
                    break
                else:
                    [h(event) for h in self._event_handlers.get(e_type, [])]

    def stop(self):
        self.stop_event.set()
        self.queue.safe_put(events.StopEventHandler())


# -- Worker classes

class Worker:
    MAX_TERMINATE_CALLED = 3
    int_handler = staticmethod(default_signal_handler)
    term_handler = staticmethod(default_signal_handler)

    def __init__(self, name, startup_event: mp.Event, shutdown_event: mp.Event, publish_q: MPQueue, event_q: MPQueue,
                 *args, **kwargs):
        self.name = name
        self.logger = logging.getLogger(f'dm.{self.name}')
        self.startup_event = startup_event
        self.shutdown_event = shutdown_event
        self.publish_q = publish_q
        self.event_q = event_q
        self.dispatcher = EventHandler(self.event_q)
        self.terminate_called = 0
        self.init_args(*args, **kwargs)

    def _init_signals(self):
        self.logger.debug("Entering init_signals")
        try:
            signal_object = init_signals(self.shutdown_event, self.int_handler, self.term_handler)
        except ValueError:
            pass
        else:
            return signal_object
        # loop = asyncio.get_event_loop()
        # for signame in {'SIGINT', 'SIGTERM'}:
        #     loop.add_signal_handler(
        #         getattr(signal, signame),
        #         functools.partial(default_async_signal_handler, signame, loop))

    def init_args(self, *args, **kwargs):
        pass

    def startup(self):
        self.logger.debug("Entering startup")
        pass

    def _startup(self):
        self.dispatcher.start()
        self.startup()

    def shutdown(self):
        self.logger.debug("Entering shutdown")
        pass

    def _shutdown(self):
        self.shutdown()
        self.dispatcher.stop()
        self.dispatcher.join()

    def _main_loop(self):
        self.logger.debug("Entering main_loop")
        while not self.shutdown_event.is_set():
            self.main_func()

    @abc.abstractmethod
    def main_func(self, *args, **kwargs):
        self.logger.debug("Entering main_func")
        raise NotImplementedError(f"{self.__class__.__name__}.main_func is not implemented")

    def run(self):
        self._init_signals()
        try:
            self._startup()
            self.startup_event.set()
            self._main_loop()
            self.logger.info("Normal Shutdown")
            self.publish_q.safe_put(events.EventMessage("SHUTDOWN", msg_src=self.name, msg="Normal"))
            return 0
        except BaseException as exc:
            # -- Catch ALL exceptions, even Terminate and Keyboard interrupt
            self.logger.error(f"Exception Shutdown: {exc}", exc_info=True)
            self.publish_q.safe_put(events.EventMessage("FATAL", msg_src=self.name, msg=exc))
            if type(exc) in (TerminateInterrupt, KeyboardInterrupt):
                sys.exit(1)
            else:
                sys.exit(2)
        finally:
            self._shutdown()


class TimerWorker(Worker):
    INTERVAL_SECS = 10
    MAX_SLEEP_SECS = 0.02

    def _main_loop(self):
        self.next_time = time.time() + self.INTERVAL_SECS
        while not self.shutdown_event.is_set():
            sleep_secs = _sleep_secs(self.MAX_SLEEP_SECS, self.next_time)
            time.sleep(sleep_secs)
            if self.next_time and time.time() > self.next_time:
                self.logger.log(1, f"Calling main_func")
                self.main_func()
                self.next_time = time.time() + self.INTERVAL_SECS


# class QueueWorker(Worker):
#     def init_args(self, args):
#         self.logger.debug(f"Entering QueueProcWorker.init_args : {args}")
#         self.work_q, = args
#
#     def _main_loop(self):
#         self.logger.debug("Entering QueueProcWorker.main_loop")
#         while not self.shutdown_event.is_set():
#             item = self.work_q.safe_get()
#             if not item:
#                 continue
#             self.logger.debug(f"QueueProcWorker.main_loop received '{item}' message")
#             if item == "END":
#                 break
#             else:
#                 self.main_func(item)


# -- Process Wrapper

def proc_worker_wrapper(proc_worker_class, name, startup_evt, shutdown_evt, publish_q, event_q, *args, **kwargs):
    proc_worker = proc_worker_class(name, startup_evt, shutdown_evt, publish_q, event_q, *args, **kwargs)
    return proc_worker.run()


class Proc:
    STARTUP_WAIT_SECS = 3
    SHUTDOWN_WAIT_SECS = 90

    def __init__(self, name: str, worker_class: t.Type[Worker], shutdown_event: mp.Event, publish_q: MPQueue,
                 event_q: MPQueue, async_loop=False, *args, **kwargs):
        self.name = name
        self.logger = logging.getLogger(f'dm.{self.name}')
        self.shutdown_event = shutdown_event
        self.startup_event = mp.Event()
        self._proc_worker = worker_class(f"{name}", self.startup_event, shutdown_event, publish_q, event_q, async_loop,
                                         *args, **kwargs)
        self.proc = mp.Process(target=self._proc_worker.run, name=name)
        self.logger.debug(f"Starting {name} process")
        self.proc.start()
        started = self.startup_event.wait(timeout=Proc.STARTUP_WAIT_SECS)
        self.logger.debug(f"{name} {'started' if started else 'NOT started'}")
        if not started:
            self.terminate()
            raise RuntimeError(f"Process {name} failed to startup after {Proc.STARTUP_WAIT_SECS} seconds")

    def __getattr__(self, item):
        return getattr(self._proc_worker, item)

    def full_stop(self, wait_time=SHUTDOWN_WAIT_SECS):
        self.logger.debug(f"Stopping process {self.name}")
        self.shutdown_event.set()
        self.proc.join(wait_time)
        if self.proc.is_alive():
            self.terminate()

    def terminate(self):
        self.logger.debug(f"Terminating process {self.name}")
        NUM_TRIES = 3
        tries = NUM_TRIES
        while tries and self.proc.is_alive():
            self.proc.terminate()
            time.sleep(0.01)
            tries -= 1

        if self.proc.is_alive():
            self.logger.error(f"Failed to terminate {self.name} after {NUM_TRIES} attempts")
            return False
        else:
            self.logger.info(f"Terminated {self.name} after {NUM_TRIES - tries} attempt(s)")
            return True


class Thread(Proc):
    SHUTDOWN_WAIT_SECS = 90

    def __init__(self, name: str, worker_class: t.Type[Worker], shutdown_event: mp.Event, publish_q: MPQueue,
                 event_q: MPQueue, async_loop=False, *args, **kwargs):
        self.name = name
        self.logger = logging.getLogger(f'dm.{self.name}')
        self.shutdown_event = shutdown_event
        self.startup_event = mp.Event()
        self._proc_worker = worker_class(f"{name}", self.startup_event, shutdown_event, publish_q, event_q,
                                         async_loop,
                                         *args, **kwargs)
        self.proc = threading.Thread(target=self._proc_worker.run, name=name)
        self.logger.debug(f"Starting {name} thread")
        self.proc.start()
        self.logger.debug(f"{name} started")

    def __getattr__(self, item):
        return getattr(self._proc_worker, item)

    def full_stop(self, wait_time=SHUTDOWN_WAIT_SECS):
        self.logger.debug(f"Stopping thread {self.name}")
        self.shutdown_event.set()
        self.proc.join(wait_time)
        if self.proc.is_alive():
            self.logger.warning(f"Thread {self.name} did not stop")

    def terminate(self):
        pass


# -- Main Wrappers
class MainContext:
    STOP_WAIT_SECS = 3.0

    def __init__(self, logger=None):

        self.logger = logging.getLogger(logger or 'dm.main')
        self.procs: t.List[Proc] = []
        self.threads: t.List[Thread] = []
        self.queues: t.List[MPQueue] = []
        self.shutdown_event = mp.Event()
        self.publish_q = MPQueue()

    def forward_events(self):
        item = True
        while item:
            item = self.publish_q.safe_get()
            if item:
                self.logger.debug(f"Spread event {item}")
                if item == events.Stop:
                    break
                [q.safe_put(item) for q in self.queues]

    def init_signals(self):
        return init_signals(self.shutdown_event, default_signal_handler, default_signal_handler)

    def start(self):
        pass

    def stop(self):
        self._stopped_procs_result = self.stop_procs()
        self._stopped_thread_result = self.stop_threads()
        self._stopped_queues_result = self.stop_queues()

    def __enter__(self):

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.exception(f"Exception: {exc_val}", exc_info=(exc_type, exc_val, exc_tb))

        self.stop()

        # -- Don't eat exceptions that reach here.
        return not exc_type

    def Proc(self, worker_class: t.Type[Worker], *args, **kwargs):
        queue = self.MPQueue()
        if 'name' in 'kwargs':
            name = kwargs.pop('name')
        else:
            name = worker_class.__name__
        proc = Proc(name, worker_class, self.shutdown_event, self.publish_q, queue, *args, **kwargs)
        self.procs.append(proc)
        return proc

    def Thread(self, worker_class: t.Type[Worker], *args, **kwargs):
        queue = self.MPQueue()
        if 'name' in 'kwargs':
            name = kwargs.pop('name')
        else:
            name = worker_class.__name__
        proc = Thread(name, worker_class, self.shutdown_event, self.publish_q, queue, *args, **kwargs)
        self.threads.append(proc)
        return proc

    def MPQueue(self, *args, **kwargs):
        q = MPQueue(*args, **kwargs)
        self.queues.append(q)
        return q

    def publish(self, event):
        [q.safe_put(event) for q in self.queues]

    def stop_procs(self):
        # self.publish(events.Stop(msg_src="stop_procs", msg="END"))
        self.shutdown_event.set()
        end_time = time.time() + self.STOP_WAIT_SECS
        num_terminated = 0
        num_failed = 0

        # -- Wait up to STOP_WAIT_SECS for all processes to complete
        for proc in self.procs:
            join_secs = _sleep_secs(self.STOP_WAIT_SECS, end_time)
            proc.proc.join(join_secs)

        # -- Clear the procs list and _terminate_ any procs that
        # have not yet exited
        still_running = []
        while self.procs:
            proc = self.procs.pop()
            if proc.proc.is_alive():
                if proc.terminate():
                    num_terminated += 1
                else:
                    still_running.append(proc)
            else:
                if hasattr(proc.proc, 'exitcode'):
                    exitcode = proc.proc.exitcode
                    if exitcode:
                        self.logger.error(f"Process {proc.name} ended with exitcode {exitcode}")
                        num_failed += 1
                    else:
                        self.logger.debug(f"Process {proc.name} stopped successfully")

        self.procs = still_running
        return num_failed, num_terminated

    def stop_threads(self):
        # self.publish(events.Stop(msg_src="stop_procs", msg="END"))
        self.shutdown_event.set()
        end_time = time.time() + self.STOP_WAIT_SECS
        num_terminated = 0
        num_failed = 0

        # -- Wait up to STOP_WAIT_SECS for all processes to complete
        for th in self.threads:
            join_secs = _sleep_secs(self.STOP_WAIT_SECS, end_time)
            th.proc.join(join_secs)

        # -- Clear the procs list and _terminate_ any procs that
        # have not yet exited
        still_running = []
        while self.threads:
            th = self.threads.pop()
            if th.proc.is_alive():
                still_running.append(th)
            else:
                num_terminated += 1

        self.threads = still_running
        return num_terminated

    def stop_queues(self):
        num_items_left = 0
        # -- Clear the queues list and close all associated queues
        for q in self.queues:
            num_items_left += sum(1 for __ in q.drain())
            q.close()

        # -- Wait for all queue threads to stop
        while self.queues:
            q = self.queues.pop(0)
            q.join_thread()
        return num_items_left
