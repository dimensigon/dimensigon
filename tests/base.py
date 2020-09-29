import threading
from unittest import mock
from unittest.case import TestCase

import flask
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import User
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import errors, create_app, db
from tests.helpers import set_test_scoped_session


def app_scope():
    try:
        return str(hash(flask._app_ctx_stack.top.app)) + str(threading.get_ident())
    except:
        return str(threading.get_ident())


class TestCaseLockBypass(TestCase):

    def run(self, result=None):
        with mock.patch('dimensigon.use_cases.lock.lock'):
            with mock.patch('dimensigon.use_cases.lock.unlock'):
                super().run(result)


class ValidateResponseMixin:

    def validate_error_response(self, resp: flask.Response, error: errors.BaseError):
        self.assertEqual(error.status_code, resp.status_code)
        self.assertDictEqual(errors.format_error_content(error), resp.get_json())


class TestDimensigonBase(TestCase, ValidateResponseMixin):

    def set_scoped_session(self, func=app_scope):
        set_test_scoped_session(db, func)

    def setUp(self) -> None:
        self.maxDiff = None
        self.set_scoped_session()
        self.app = create_app('test')
        self.app.config['SECURIZER'] = False
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        User.set_initial()
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
