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


class TestCaseLockBypass(TestCase):

    def run(self, result=None):
        with mock.patch('dimensigon.use_cases.lock.lock'):
            with mock.patch('dimensigon.use_cases.lock.unlock'):
                super().run(result)


class ValidateResponseMixin:

    def validate_error_response(self, resp: flask.Response, error: errors.BaseError):
        self.assertEqual(error.status_code, resp.status_code)
        self.assertDictEqual(errors.format_error_content(error), resp.get_json())


class TestDimensigonBase(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.dim = generate_dimension_json_data()

    def set_scoped_session(self, func=app_scope):
        set_test_scoped_session(db, func)

    def setUp(self) -> None:
        self.maxDiff = None
        self.set_scoped_session()
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        d = Dimension.from_json(self.dim)
        d.current = True
        db.session.add(d)
        set_initial()
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()


class OneNodeMixin:

    @classmethod
    def setUpClass(cls) -> None:
        cls.dim = generate_dimension_json_data()

    def set_scoped_session(self, func=app_scope):
        set_test_scoped_session(db, func)

    def fill_database(self):
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
        self.app.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()

        self.fill_database()

        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()


class TwoNodeMixin:

    @classmethod
    def setUpClass(cls) -> None:
        cls.dim = generate_dimension_json_data()

    def set_scoped_session(self, func=app_scope):
        set_test_scoped_session(db, func)

    def set_routing(self, node):
        if node == 'node1':
            Route(self.s2, self.g12)
        elif node == 'node2':
            Route(self.s1, self.g11)


    def fill_database(self, app: Flask):
        node = app.config['SERVER_NAME']
        with app.app_context():
            db.create_all()
            set_initial(server=False, user=True, action_template=True)
            d = Dimension.from_json(self.dim)
            d.current = True
            self.s1 = Server('node1', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000001',
                        me=node == 'node1')
            self.g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000, dns=self.s1.name)
            self.s2 = Server('node2', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000002',
                        me=node == 'node2')
            self.g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=self.s2, port=5000, dns=self.s2.name)

            self.set_routing(node)

            db.session.add_all([d, self.s1, self.s2])
            db.session.commit()

    def setUp(self):
        """Create and configure a new app instance for each test."""
        self.maxDiff = None
        # create the app with common test config
        self.set_scoped_session()
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()

        self.app2 = create_app('test')
        self.app2.config['SERVER_NAME'] = 'node2'
        self.app2_context = self.app2.app_context()
        self.client2 = self.app2.test_client()

        self.fill_database(self.app)

        self.fill_database(self.app2)

        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        with self.app2_context:
            db.session.remove()
            db.drop_all()


class ThreeNodeMixin:

    @classmethod
    def setUpClass(cls) -> None:
        cls.dim = generate_dimension_json_data()

    def set_scoped_session(self, func=app_scope):
        set_test_scoped_session(db, func)

    def set_routing(self, node):
        if node == 'node1':
            Route(self.s2, self.g12)
            Route(self.s3, self.g13)
        elif node == 'node2':
            Route(self.s1, self.g11)
            Route(self.s3, self.g13)
        elif node == 'node3':
            Route(self.s1, self.g11)
            Route(self.s2, self.g12)

    def fill_database(self, app: Flask):
        node = app.config['SERVER_NAME']
        with app.app_context():
            db.create_all()
            set_initial(server=False, user=True, action_template=True)
            d = Dimension.from_json(self.dim)
            d.current = True
            self.s1 = Server('node1', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000001',
                             me=node == 'node1')
            self.g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000, dns=self.s1.name)
            self.s2 = Server('node2', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000002',
                             me=node == 'node2')
            self.g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=self.s2, port=5000, dns=self.s2.name)
            self.s3 = Server('node3', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000003',
                             me=node == 'node3')
            self.g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=self.s3, port=5000, dns=self.s3.name)

            self.set_routing(node)

            db.session.add_all([d, self.s1, self.s2, self.s3])
            db.session.commit()

    def setUp(self):
        """Create and configure a new app instance for each test."""
        self.maxDiff = None
        # create the app with common test config
        self.set_scoped_session()
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()

        self.app2 = create_app('test')
        self.app2.config['SERVER_NAME'] = 'node2'
        self.app2_context = self.app2.app_context()
        self.client2 = self.app2.test_client()

        self.app3 = create_app('test')
        self.app3.config['SERVER_NAME'] = 'node3'
        self.app3_context = self.app3.app_context()
        self.client3 = self.app3.test_client()

        self.fill_database(self.app2)

        self.fill_database(self.app3)

        self.fill_database(self.app)

        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        with self.app2_context:
            db.session.remove()
            db.drop_all()

        with self.app3_context:
            db.session.remove()
            db.drop_all()