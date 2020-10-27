import functools
from unittest import mock
from unittest.case import TestCase

import flask
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import User
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import errors, create_app, db
from tests.helpers import set_test_scoped_session, app_scope


class TestCaseLockBypass(TestCase):

    def run(self, result=None):
        with mock.patch('dimensigon.use_cases.lock.lock'):
            with mock.patch('dimensigon.use_cases.lock.unlock'):
                super().run(result)


class ValidateResponseMixin:

    def validate_error_response(self, resp: flask.Response, error: errors.BaseError):
        self.assertEqual(error.status_code, resp.status_code)
        self.assertDictEqual(errors.format_error_content(error), resp.get_json())


class AppScopedSession:

    # def __new__(cls, *args, **kwargs):
    #     obj = super(AppScopedSession, cls).__new__(cls)
    #     if hasattr(obj, 'setUp') and callable(getattr(obj, 'setUp')):
    #         obj.setUp = AppScopedSession.wrapper_set_scope(obj, obj.setUp, kwargs.pop('db'))
    #     return obj
    #
    # def wrapper_set_scope(self, func, db_):
    #     @functools.wraps(func)
    #     def wrapper(*args, **kwargs):
    #         set_test_scoped_session(db_, app_scope)
    #         dto = func(*args, **kwargs)
    #         return dto
    #
    #     return wrapper

    def set_test_scoped_session(self, db_):
        set_test_scoped_session(db_, app_scope)


class TestDimensigonBase(TestCase, ValidateResponseMixin):

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
