import os
import unittest
from unittest import mock
from unittest.case import TestCase

import flask
from flask import Flask
from flask_jwt_extended import create_access_token

from dimensigon import defaults
from dimensigon.domain.entities import User, Dimension, Server, Gate, Route
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import errors, create_app, db
from tests.helpers import set_test_scoped_session, generate_dimension_json_data, app_scope


class TestCaseLockBypassMixin:

    def run(self, result=None):
        with mock.patch('dimensigon.use_cases.lock.lock'):
            with mock.patch('dimensigon.use_cases.lock.unlock'):
                with mock.patch('dimensigon.use_cases.helpers.current_app') as mock_app:
                    mock_app.dm.cluster_manager.get_alive.return_value = []
                    super().run(result)


class ValidateResponseMixin:
    def validate_error_response(self, resp: flask.Response, error: errors.BaseError):
        if hasattr(self, 'assertEqual') and hasattr(self, 'assertDictEqual'):
            self.assertEqual(error.status_code, resp.status_code)
            self.assertDictEqual(errors.format_error_content(error), resp.get_json())


class TestBase:
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
    db_uris = []

    def _fill_database(self):
        db.create_all()
        set_initial(server=False, user=True, action_template=True)
        d = Dimension.from_json(self.dim)
        d.current = True
        self.s1 = Server('node1', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000001',
                         me=True)
        self.g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000, dns=self.s1.name)

        db.session.add_all([d, self.s1])
        db.session.commit()

    def setUp(self) -> None:
        self.maxDiff = None
        self.set_scoped_session()
        self.app = create_app('test')
        if self.db_uris:
            self.app.config['SQLALCHEMY_DATABASE_URI'] = self.db_uris[0]
        self.app.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()

        self._fill_database()

        self.auth = HTTPBearerAuth(create_access_token(User.get_by_name('root').id))

    def tearDown(self) -> None:
        self.remove_db()
        self.app_context.pop()


class TwoNodeMixin(TestBase):
    db_uris = []

    def _fill_database(self, app: Flask):
        node = app.config['SERVER_NAME']

        with app.app_context():
            db.create_all()
            set_initial(server=False, user=True, action_template=True)
            d = Dimension.from_json(self.dim)
            d.current = True
            s1 = Server('node1', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000001',
                        me=node == 'node1')
            g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=s1, port=5000, dns=s1.name)
            s2 = Server('node2', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000002',
                        me=node == 'node2')
            g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)

            if node == 'node1':
                Route(s2, g12)
            elif node == 'node2':
                Route(s1, g11)

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
        self.app.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()

        self.app2 = create_app('test')
        if self.db_uris:
            self.app2.config['SQLALCHEMY_DATABASE_URI'] = self.db_uris[1]
        self.app2.config['SERVER_NAME'] = 'node2'
        self.app2_context = self.app2.app_context()
        self.client2 = self.app2.test_client()

        self._fill_database(self.app)

        self._fill_database(self.app2)

        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))

    def tearDown(self) -> None:
        self.remove_db()
        self.app_context.pop()

        with self.app2_context:
            self.remove_db()


class ThreeNodeMixin(TestBase):
    db_uris = []

    def _fill_database(self, app: Flask):
        node = app.config['SERVER_NAME']
        with app.app_context():
            db.create_all()
            set_initial(server=False, user=True, action_template=True)
            d = Dimension.from_json(self.dim)
            d.current = True
            s1 = Server('node1', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000001',
                        me=node == 'node1')
            g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=s1, port=5000, dns=s1.name)
            s2 = Server('node2', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000002',
                        me=node == 'node2')
            g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
            s3 = Server('node3', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000003',
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
        self.app.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()

        self.app2 = create_app('test')
        if self.db_uris:
            self.app2.config['SQLALCHEMY_DATABASE_URI'] = self.db_uris[1]
        self.app2.config['SERVER_NAME'] = 'node2'
        self.app2_context = self.app2.app_context()
        self.client2 = self.app2.test_client()

        self.app3 = create_app('test')
        if self.db_uris:
            self.app3.config['SQLALCHEMY_DATABASE_URI'] = self.db_uris[3]
        self.app3.config['SERVER_NAME'] = 'node3'
        self.app3_context = self.app3.app_context()
        self.client3 = self.app3.test_client()

        self._fill_database(self.app2)

        self._fill_database(self.app3)

        self._fill_database(self.app)

        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))

    def tearDown(self) -> None:
        self.remove_db()
        self.app_context.pop()

        with self.app2_context:
            self.remove_db()

        with self.app3_context:
            self.remove_db()


class TestCaseLockBypass(TestCaseLockBypassMixin, TestCase):
    pass


class TestDimensigonBase(OneNodeMixin, TestCase):
    ...
    # def setUp(self) -> None:
    #     super().setUp()
    #     # set_initial()


class AsyncMock(unittest.mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
