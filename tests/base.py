import inspect
import os
import typing as t
import unittest
from contextlib import contextmanager
from unittest import mock
from unittest.case import TestCase

import flask
import responses
from aioresponses import aioresponses
from flask import Flask
from flask_jwt_extended import create_access_token
from sqlalchemy import event

from dimensigon import defaults
from dimensigon.domain.entities import User, Dimension, Server, Gate, Route, receive_after_commit
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.domain.entities.user import ROOT
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import errors, create_app, db
from tests.helpers import set_test_scoped_session, generate_dimension_json_data, app_scope, set_callbacks, \
    remove_db_file


class LockBypassMixin:

    def run(self, result=None):
        with mock.patch('dimensigon.use_cases.lock.lock'):
            with mock.patch('dimensigon.use_cases.lock.unlock'):
                with mock.patch('dimensigon.use_cases.lock.get_servers_from_scope') as mock_app:
                    mock_app.dm.cluster_manager.get_alive.return_value = []
                    super().run(result)


class ValidateResponseMixin:
    def validate_error_response(self, resp: flask.Response, error: t.Union[errors.BaseError, t.Type[Exception]]):
        def assertEqual(x, y):
            assert x == y

        def assertDictEqual(x, y):
            assert str(x) == str(y)

        assertEqual = self.assertEqual if hasattr(self, 'assertEqual') else assertEqual
        assertDictEqual = self.assertDictEqual if hasattr(self, 'assertDictEqual') else assertDictEqual

        if inspect.isclass(error):
            assertEqual(error.__qualname__, resp.get_json().get('error').get('type'))
        else:
            assertEqual(error.status_code, resp.status_code)
            assertDictEqual(errors.format_error_content(error), resp.get_json())


class TestBase:
    maxDiff = None
    scopefunc = app_scope

    def set_scoped_session(self):
        set_test_scoped_session(db, self.scopefunc)

    @classmethod
    def setUpClass(cls) -> None:
        cls.dim = generate_dimension_json_data()

    @staticmethod
    def remove_db():
        db.session.remove()
        db.drop_all()
        engine = db.get_engine()
        if engine.url.drivername == 'sqlite':
            try:
                os.remove(engine.url.database)
            except:
                pass

    def fill_database(self):
        pass

    def generate_auth(self):
        u = User.query.get(ROOT)
        if u:
            self.auth = HTTPBearerAuth(create_access_token(u.id))


class FlaskAppMixin(TestBase):
    def setUp(self):
        self.maxDiff = None
        self.set_scoped_session()
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'me'
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()
        db.create_all()

    def tearDown(self) -> None:
        self.remove_db()
        self.app_context.pop()


class OneNodeMixin(TestBase):
    SERVER = '00000000-0000-0000-0000-000000000001'
    db_uris = []
    initials = dict(server=False)

    def _fill_database(self):
        with mock.patch('dimensigon.domain.entities.get_now') as mock_get_now:
            mock_get_now.return_value = defaults.INITIAL_DATEMARK
            db.create_all()
            event.listen(db.session, 'after_commit', receive_after_commit)

            set_initial(**self.initials)
            d = Dimension.from_json(self.dim)
            d.current = True
            self.s1 = Server('node1', created_on=defaults.INITIAL_DATEMARK, id=self.SERVER,
                             me=True)
            self.g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000, dns=self.s1.name)
            self.fill_database()
            db.session.add_all([d, self.s1])
            db.session.commit()

    def setUp(self) -> None:
        self.maxDiff = None
        self.set_scoped_session()
        self.app = create_app('test')
        if self.db_uris:
            self.app.config['SQLALCHEMY_DATABASE_URI'] = self.db_uris[0]
            remove_db_file(self.db_uris[0])
        self.app.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()

        self._fill_database()
        self.generate_auth()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        self.remove_db()
        self.app_context.pop()


class TwoNodeMixin(TestBase):
    SERVER1 = '00000000-0000-0000-0000-000000000001'
    SERVER2 = '00000000-0000-0000-0000-000000000002'
    db_uris = []
    initials = dict(server=False)

    def _fill_database(self, app: Flask):
        with mock.patch('dimensigon.domain.entities.get_now') as mock_get_now:
            mock_get_now.return_value = defaults.INITIAL_DATEMARK
            node = app.config['SERVER_NAME']

            with app.app_context():
                db.create_all()
                event.listen(db.session, 'after_commit', receive_after_commit)
                set_initial(**self.initials)
                d = Dimension.from_json(self.dim)
                d.current = True
                s1 = Server('node1', created_on=defaults.INITIAL_DATEMARK, id=self.SERVER1,
                            me=node == 'node1')
                g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=s1, port=5000, dns=s1.name)
                s2 = Server('node2', created_on=defaults.INITIAL_DATEMARK, id=self.SERVER2,
                            me=node == 'node2')
                g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)

                if node == 'node1':
                    Route(s2, g12)
                elif node == 'node2':
                    Route(s1, g11)

                self.fill_database()
                db.session.add_all([d, s1, s2])
                db.session.commit()
            if node == 'node1':
                self.s1, self.s2 = db.session.merge(s1), db.session.merge(s2)


    def setUp(self):
        """Create and configure a new app instance for each test."""
        self.maxDiff = None
        # create the app with common test config
        self.set_scoped_session()
        self.app = create_app('test')
        if self.db_uris:
            self.app.config['SQLALCHEMY_DATABASE_URI'] = self.db_uris[0]
            remove_db_file(self.db_uris[0])
        self.app.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()

        self.app2 = create_app('test')
        if self.db_uris:
            self.app2.config['SQLALCHEMY_DATABASE_URI'] = self.db_uris[1]
            remove_db_file(self.db_uris[1])
        self.app2.config['SERVER_NAME'] = 'node2'
        self.app2_context = self.app2.app_context()
        self.client2 = self.app2.test_client()

        self._fill_database(self.app)

        self._fill_database(self.app2)
        self.generate_auth()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        self.remove_db()
        self.app_context.pop()

        with self.app2_context:
            self.remove_db()


class ThreeNodeMixin(TestBase):
    SERVER1 = '00000000-0000-0000-0000-000000000001'
    SERVER2 = '00000000-0000-0000-0000-000000000002'
    SERVER3 = '00000000-0000-0000-0000-000000000003'
    db_uris = []
    initials = dict(server=False)

    def _fill_database(self, app: Flask):
        with mock.patch('dimensigon.domain.entities.get_now') as mock_get_now:
            mock_get_now.return_value = defaults.INITIAL_DATEMARK
            node = app.config['SERVER_NAME']
            with app.app_context():
                db.create_all()
                event.listen(db.session, 'after_commit', receive_after_commit)
                set_initial(**self.initials)
                d = Dimension.from_json(self.dim)
                d.current = True
                s1 = Server('node1', created_on=defaults.INITIAL_DATEMARK, id=self.SERVER1,
                            me=node == 'node1')
                g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=s1, port=5000, dns=s1.name)
                s2 = Server('node2', created_on=defaults.INITIAL_DATEMARK, id=self.SERVER2,
                            me=node == 'node2')
                g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
                s3 = Server('node3', created_on=defaults.INITIAL_DATEMARK, id=self.SERVER3,
                            me=node == 'node3')
                g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)

                if node == 'node1':
                    Route(s2, g12)
                    Route(s3, g13)
                elif node == 'node2':
                    Route(s1, g11)
                    Route(s3, g13)
                elif node == 'node3':
                    Route(s1, g11)
                    Route(s2, g12)

                self.fill_database()
                db.session.add_all([d, s1, s2, s3])
                db.session.commit()
            if node == 'node1':
                self.s1, self.s2, self.s3 = db.session.merge(s1), db.session.merge(s2), db.session.merge(s3)

    def setUp(self):
        """Create and configure a new app instance for each test."""
        self.maxDiff = None
        # create the app with common test config
        self.set_scoped_session()
        self.app = create_app('test')
        if self.db_uris:
            self.app.config['SQLALCHEMY_DATABASE_URI'] = self.db_uris[0]
            remove_db_file(self.db_uris[0])
        self.app.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()

        self.app2 = create_app('test')
        if self.db_uris:
            self.app2.config['SQLALCHEMY_DATABASE_URI'] = self.db_uris[1]
            remove_db_file(self.db_uris[1])
        self.app2.config['SERVER_NAME'] = 'node2'
        self.app2_context = self.app2.app_context()
        self.client2 = self.app2.test_client()

        self.app3 = create_app('test')
        if self.db_uris:
            self.app3.config['SQLALCHEMY_DATABASE_URI'] = self.db_uris[2]
            remove_db_file(self.db_uris[2])
        self.app3.config['SERVER_NAME'] = 'node3'
        self.app3_context = self.app3.app_context()
        self.client3 = self.app3.test_client()

        self._fill_database(self.app2)

        self._fill_database(self.app3)

        self._fill_database(self.app)
        self.generate_auth()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        self.remove_db()
        self.app_context.pop()

        with self.app2_context:
            self.remove_db()

        with self.app3_context:
            self.remove_db()


@contextmanager
def virtual_network(*apps):
    r = responses.RequestsMock(assert_all_requests_are_fired=False)
    r = r.__enter__()
    ar = aioresponses()
    ar = ar.__enter__()
    set_callbacks([(app.config['SERVER_NAME'], app.test_client()) for app in apps], ar=ar, r=r)
    yield r, ar
    r.__exit__(None, None, None)
    ar.__exit__(None, None, None)


class VirtualNetworkMixin:

    def setUp(self):
        super().setUp()
        self.apps = []
        if hasattr(self, 'app'):
            self.apps.append(self.app)
        if hasattr(self, 'app2'):
            self.apps.append(self.app2)
        if hasattr(self, 'app3'):
            self.apps.append(self.app3)

        r = responses.RequestsMock(assert_all_requests_are_fired=False)
        self._r = r.__enter__()
        ar = aioresponses()
        self._ar = ar.__enter__()
        set_callbacks([(app.config['SERVER_NAME'], app.test_client()) for app in self.apps], ar=self._ar, r=self._r)

    def tearDown(self):
        self._r.__exit__(None, None, None)
        self._ar.__exit__(None, None, None)
        super().tearDown()


class TestCaseLockBypass(LockBypassMixin, TestCase):
    pass


class TestDimensigonBase(OneNodeMixin, TestCase):
    ...
    # def setUp(self) -> None:
    #     super().setUp()
    #     # set_initial()


class TestResourceBase(OneNodeMixin, LockBypassMixin, ValidateResponseMixin, TestCase):
    ...


class AsyncMock(unittest.mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
