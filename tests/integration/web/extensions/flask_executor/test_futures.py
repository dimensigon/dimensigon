import concurrent.futures
import time
from unittest import TestCase

from flask import Flask

from dimensigon.web.extensions.flask_executor.executor import Executor
from dimensigon.web.extensions.flask_executor.futures import FutureCollection, FutureProxy
from dimensigon.web.extensions.flask_executor.helpers import InstanceProxy


def fib(n):
    if n <= 2:
        return 1
    else:
        return fib(n - 1) + fib(n - 2)


class TestFutures(TestCase):

    def test_plain_future(self):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        futures = FutureCollection()
        future = executor.submit(fib, 33)
        futures.add('fibonacci', future)
        assert futures.done('fibonacci') is False
        assert futures._state('fibonacci') is not None
        assert future in futures
        futures.pop('fibonacci')
        assert future not in futures

    def test_missing_future(self):
        futures = FutureCollection()
        assert futures.running('test') is None

    def test_duplicate_add_future(self):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        futures = FutureCollection()
        future = executor.submit(fib, 33)
        futures.add('fibonacci', future)
        try:
            futures.add('fibonacci', future)
        except ValueError:
            assert True
        else:
            assert False

    def test_futures_max_length(self):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        futures = FutureCollection(max_length=10)
        future = executor.submit(pow, 2, 4)
        futures.add(0, future)
        assert future in futures
        assert len(futures) == 1
        for i in range(1, 11):
            futures.add(i, executor.submit(pow, 2, 4))
        assert len(futures) == 10
        assert future not in futures

    def test_future_proxy(self):
        app = Flask(__name__)
        executor = Executor(app)
        with app.test_request_context(''):
            future = executor.submit(pow, 2, 4)
        # Test if we're returning a subclass of Future
        assert isinstance(future, concurrent.futures.Future)
        assert isinstance(future, FutureProxy)
        concurrent.futures.wait([future])
        # test standard Future methods and attributes
        assert future._state == concurrent.futures._base.FINISHED
        assert future.done()
        assert future.exception(timeout=0) is None

    def test_add_done_callback(self):
        """Exceptions thrown in callbacks can't be easily caught and make it hard
        to test for callback failure. To combat this, a global variable is used to
        store the value of an exception and test for its existence.
        """
        app = Flask(__name__)
        executor = Executor(app)
        global exception
        exception = None
        with app.test_request_context(''):
            future = executor.submit(time.sleep, 0.5)

            def callback(future):
                global exception
                try:
                    executor.submit(time.sleep, 0)
                except RuntimeError as e:
                    exception = e

            future.add_done_callback(callback)
        concurrent.futures.wait([future])
        assert exception is None

    def test_instance_proxy(self):
        class TestProxy(InstanceProxy):
            pass

        x = TestProxy(concurrent.futures.Future())
        assert isinstance(x, concurrent.futures.Future)
        assert 'TestProxy' in repr(x)
        assert 'Future' in repr(x)
