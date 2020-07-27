import concurrent.futures
import random
import time
from unittest import TestCase

from flask import Flask, current_app, g, request

from dimensigon.web.extensions.flask_executor.executor import Executor, propagate_exceptions_callback


def fib(n):
    if n <= 2:
        return 1
    else:
        return fib(n - 1) + fib(n - 2)


def app_context_test_value(_=None):
    return current_app.config['TEST_VALUE']


def request_context_test_value(_=None):
    return request.test_value


def g_context_test_value(_=None):
    return g.test_value


def fail():
    time.sleep(0.1)
    raise RuntimeError


class Test(TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        
    def test_init(self):
        self.app = Flask(__name__)
        executor = Executor(self.app)
        assert 'executor' in self.app.extensions
        assert isinstance(executor, concurrent.futures._base.Executor)
        assert isinstance(executor._self, concurrent.futures._base.Executor)
        assert getattr(executor, 'shutdown')

    def test_factory_init(self):
        self.app = Flask(__name__)
        executor = Executor()
        executor.init_app(self.app)
        assert 'executor' in self.app.extensions
        assert isinstance(executor._self, concurrent.futures._base.Executor)

    def test_thread_executor_init(self):
        self.app = Flask(__name__)
        self.app.config['EXECUTOR_TYPE'] = 'thread'
        executor = Executor(self.app)
        assert isinstance(executor._self, concurrent.futures.ThreadPoolExecutor)
        assert isinstance(executor, concurrent.futures.ThreadPoolExecutor)

    def test_process_executor_init(self):
        self.app = Flask(__name__)
        self.app.config['EXECUTOR_TYPE'] = 'process'
        executor = Executor(self.app)
        assert isinstance(executor._self, concurrent.futures.ProcessPoolExecutor)
        assert isinstance(executor, concurrent.futures.ProcessPoolExecutor)

    def test_default_executor_init(self):
        self.app = Flask(__name__)
        executor = Executor(self.app)
        assert isinstance(executor._self, concurrent.futures.ThreadPoolExecutor)

    def test_invalid_executor_init(self):
        self.app = Flask(__name__)
        self.app.config['EXECUTOR_TYPE'] = 'invalid_value'
        try:
            executor = Executor(self.app)
        except ValueError:
            assert True
        else:
            assert False

    def test_submit(self):
        self.app = Flask(__name__)
        executor = Executor(self.app)
        with self.app.test_request_context(''):
            future = executor.submit(fib, 5)
        assert future.result() == fib(5)

    def test_max_workers(self):
        self.app = Flask(__name__)
        EXECUTOR_MAX_WORKERS = 10
        self.app.config['EXECUTOR_MAX_WORKERS'] = EXECUTOR_MAX_WORKERS
        executor = Executor(self.app)
        assert executor._max_workers == EXECUTOR_MAX_WORKERS
        assert executor._self._max_workers == EXECUTOR_MAX_WORKERS

    def test_thread_decorator_submit(self):
        
        self.app.config['EXECUTOR_TYPE'] = 'thread'
        executor = Executor(self.app)

        @executor.job
        def decorated(n):
            return fib(n)

        with self.app.test_request_context(''):
            future = decorated.submit(5)
        assert future.result() == fib(5)

    def test_thread_decorator_submit_stored(self):
        self.app.config['EXECUTOR_TYPE'] = 'thread'
        executor = Executor(self.app)

        @executor.job
        def decorated(n):
            return fib(n)

        with self.app.test_request_context():
            future = decorated.submit_stored('fibonacci', 35)
        assert executor.futures.done('fibonacci') is False
        assert future in executor.futures
        executor.futures.pop('fibonacci')
        assert future not in executor.futures

    def test_thread_decorator_map(self):
        iterable = list(range(5))
        self.app.config['EXECUTOR_TYPE'] = 'thread'
        executor = Executor(self.app)

        @executor.job
        def decorated(n):
            return fib(n)

        with self.app.test_request_context(''):
            results = decorated.map(iterable)
        for i, r in zip(iterable, results):
            assert fib(i) == r

    def test_process_decorator(self):
        ''' Using decorators should fail with a TypeError when using the ProcessPoolExecutor '''
        self.app.config['EXECUTOR_TYPE'] = 'process'
        executor = Executor(self.app)
        try:
            @executor.job
            def decorated(n):
                return fib(n)
        except TypeError:
            pass
        else:
            assert 0

    def test_submit_app_context(self):
        test_value = random.randint(1, 101)
        self.app.config['TEST_VALUE'] = test_value
        executor = Executor(self.app)
        with self.app.test_request_context(''):
            future = executor.submit(app_context_test_value)
        assert future.result() == test_value

    def test_submit_g_context_process(self):
        test_value = random.randint(1, 101)
        executor = Executor(self.app)
        with self.app.test_request_context(''):
            g.test_value = test_value
            future = executor.submit(g_context_test_value)
        assert future.result() == test_value

    def test_submit_request_context(self):
        test_value = random.randint(1, 101)
        executor = Executor(self.app)
        with self.app.test_request_context(''):
            request.test_value = test_value
            future = executor.submit(request_context_test_value)
        assert future.result() == test_value

    def test_map_app_context(self):
        test_value = random.randint(1, 101)
        iterator = list(range(5))
        self.app.config['TEST_VALUE'] = test_value
        executor = Executor(self.app)
        with self.app.test_request_context(''):
            results = executor.map(app_context_test_value, iterator)
        for r in results:
            assert r == test_value

    def test_map_g_context_process(self):
        test_value = random.randint(1, 101)
        iterator = list(range(5))
        executor = Executor(self.app)
        with self.app.test_request_context(''):
            g.test_value = test_value
            results = executor.map(g_context_test_value, iterator)
        for r in results:
            assert r == test_value

    def test_map_request_context(self):
        test_value = random.randint(1, 101)
        iterator = list(range(5))
        executor = Executor(self.app)
        with self.app.test_request_context('/'):
            request.test_value = test_value
            results = executor.map(request_context_test_value, iterator)
        for r in results:
            assert r == test_value

    def test_executor_stored_future(self):
        executor = Executor(self.app)
        with self.app.test_request_context():
            future = executor.submit_stored('fibonacci', fib, 35)
        assert executor.futures.done('fibonacci') is False
        assert future in executor.futures
        executor.futures.pop('fibonacci')
        assert future not in executor.futures

    def test_set_max_futures(self):
        self.app.config['EXECUTOR_FUTURES_MAX_LENGTH'] = 10
        executor = Executor(self.app)
        assert executor.futures.max_length == self.app.config['EXECUTOR_FUTURES_MAX_LENGTH']

    def test_named_executor(self):
        name = 'custom'
        EXECUTOR_MAX_WORKERS = 5
        CUSTOM_EXECUTOR_MAX_WORKERS = 10
        self.app.config['EXECUTOR_MAX_WORKERS'] = EXECUTOR_MAX_WORKERS
        self.app.config['CUSTOM_EXECUTOR_MAX_WORKERS'] = CUSTOM_EXECUTOR_MAX_WORKERS
        executor = Executor(self.app)
        custom_executor = Executor(self.app, name=name)
        assert 'executor' in self.app.extensions
        assert name + 'executor' in self.app.extensions
        assert executor._self._max_workers == EXECUTOR_MAX_WORKERS
        assert executor._max_workers == EXECUTOR_MAX_WORKERS
        assert custom_executor._self._max_workers == CUSTOM_EXECUTOR_MAX_WORKERS
        assert custom_executor._max_workers == CUSTOM_EXECUTOR_MAX_WORKERS

    def test_named_executor_submit(self):
        name = 'custom'
        custom_executor = Executor(self.app, name=name)
        with self.app.test_request_context(''):
            future = custom_executor.submit(fib, 5)
        assert future.result() == fib(5)

    def test_named_executor_name(self):
        name = 'invalid name'
        try:
            executor = Executor(self.app, name=name)
        except ValueError:
            assert True
        else:
            assert False

    def test_default_done_callback(self):
        executor = Executor(self.app)

        def callback(future):
            setattr(future, 'test', 'test')

        executor.add_default_done_callback(callback)
        with self.app.test_request_context('/'):
            future = executor.submit(fib, 5)
            concurrent.futures.wait([future])
            assert hasattr(future, 'test')

    def test_propagate_exception_callback(self):
        self.app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = True
        executor = Executor(self.app)
        with self.assertRaises(RuntimeError):
            with self.app.test_request_context('/'):
                future = executor.submit(fail)
                assert propagate_exceptions_callback in future._done_callbacks
                concurrent.futures.wait([future])
                propagate_exceptions_callback(future)

    def test_coerce_config_types(self):
        self.app.config['EXECUTOR_MAX_WORKERS'] = '5'
        self.app.config['EXECUTOR_FUTURES_MAX_LENGTH'] = '10'
        self.app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = 'true'
        executor = Executor(self.app)
        with self.app.test_request_context():
            future = executor.submit_stored('fibonacci', fib, 35)

    def test_shutdown_executor(self):
        executor = Executor(self.app)
        assert executor._shutdown is False
        executor.shutdown()
        assert executor._shutdown is True

    def test_pre_init_executor(self):
        executor = Executor()

        @executor.job
        def decorated(n):
            return fib(n)

        assert executor
        executor.init_app(self.app)
        with self.app.test_request_context(''):
            future = decorated.submit(5)
        assert future.result() == fib(5)
