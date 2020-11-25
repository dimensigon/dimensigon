import functools
import multiprocessing as mp
import os
import signal
import sys

from dataclasses import dataclass


@dataclass
class Token:
    """
    Class that saves relation between a sent message and its asynchronous return.
    """
    id: int
    source: str
    destination: str

    @property
    def uid(self):
        return self.source + '.' + self.destination + '.' + str(self.id)


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


class Process:
    MAX_TERMINATE_CALLED = 3
    int_handler = staticmethod(default_signal_handler)
    term_handler = staticmethod(default_signal_handler)
    _logger = None

    def __init__(self, shutdown_event, name=None):
        self._stop = shutdown_event
        self.name = name or self.__class__.__name__
        self.process = mp.Process(target=self._run, name=self.name)

    def _init_signals(self):
        signal_object = init_signals(self._stop, self.int_handler, self.term_handler)
        return signal_object

    def _run(self):
        self._logger.info(f'Starting {self.name} ({os.getpid()})')
        if isinstance(self.process, mp.Process):
            self._init_signals()
        try:
            self._main()
        except (TerminateInterrupt, KeyboardInterrupt):
            sys.exit(1)
        except Exception:
            self._logger.exception(f"Error while executing {self.name}")
        finally:
            self._shutdown()
        self._logger.info(f"{self.name} stopped")

    def _main(self):
        raise NotImplemented

    def _shutdown(self):
        raise NotImplemented

    def start(self):
        self.process.start()
