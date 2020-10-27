import threading
from unittest import mock
from unittest.case import TestCase

import flask
from dimensigon.domain.entities.bootstrap import set_initial
from flask_jwt_extended import create_access_token

from dimensigon import defaults
from dimensigon.domain.entities import User, Dimension, Server, Gate, Route, Locker
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import errors, create_app, db
from tests.helpers import set_test_scoped_session, generate_dimension_json_data


def app_scope():
    try:
        return str(hash(flask._app_ctx_stack.top.app)) + str(threading.get_ident())
    except:
        return str(threading.get_ident())

def request_scope():
    try:
        return str(hash(flask._request_ctx_stack.top.request)) + str(hash(flask._app_ctx_stack.top.app)) + str(threading.get_ident())
    except:
        return app_scope()

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
        s1 = Server('node1', created_on=defaults.INITIAL_DATEMARK, id='00000000-0000-0000-0000-000000000001',
                    me=True)
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=s1, port=5000, dns=s1.name)
        self.s1 = s1
        db.session.add_all([d, s1])
        db.session.commit()

    def setUp(self) -> None:
        self.maxDiff = None
        set_test_scoped_session(db)
        self.app = create_app('test')
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

    def fill_database(self, node):
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
            self.s1 = s1
            self.s2 = s2
            Route(s2, g12)
        elif node == 'node2':
            Route(s1, g11)

        db.session.add_all([d, s1, s2])
        db.session.commit()

    def setUp(self):
        """Create and configure a new app instance for each test."""
        self.maxDiff = None
        # create the app with common test config
        set_test_scoped_session(db)
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.client = self.app.test_client()
        self.app_context.push()

        self.app2 = create_app('test')
        self.app2_context = self.app2.app_context()
        self.client2 = self.app2.test_client()

        self.fill_database('node1')

        with self.app2_context:
            self.fill_database('node2')

        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        with self.app2_context:
            db.session.remove()
            db.drop_all()
