from unittest import TestCase

from flask import url_for
from flask_jwt_extended import create_access_token
from werkzeug.exceptions import InternalServerError

from dimensigon.domain.entities import User
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import create_app, db, errors


class TestApi(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app.config['DEBUG'] = True
        self.app.config['TESTING'] = False
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

        db.create_all()
        set_initial()
        u = User('test')
        db.session.add(u)
        self.auth = HTTPBearerAuth(create_access_token(u.id))

        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_validation_error(self):
        def raise_error():
            raise errors.ValidationError('error content', schema={})

        self.app.add_url_rule('/error', 'error', raise_error)
        resp = self.client.get(url_for('error'), json={}, headers=self.auth.header)

        self.assertEqual(400, resp.status_code)
        self.assertDictEqual(
            {'error': {'type': 'ValidationError', 'message': 'error content', 'schema': {}, 'path': []}},
            resp.get_json())

    def test_base_error(self):
        def raise_error():
            raise errors.GenericError('error content', some='payload')

        self.app.add_url_rule('/error', 'error', raise_error)

        resp = self.client.get(url_for('error'), json={}, headers=self.auth.header)

        self.assertEqual(400, resp.status_code)
        self.assertDictEqual({'error': {'type': 'GenericError', 'message': "error content", 'some': 'payload'}},
                             resp.get_json())

    def test_internal_server_error(self):
        self.app.config['PROPAGATE_EXCEPTIONS'] = False

        def raise_error():
            raise RuntimeError('error content')

        self.app.add_url_rule('/error', 'error', raise_error)
        resp = self.client.get(url_for('error'), json={}, headers=self.auth.header)

        self.assertEqual(500, resp.status_code)
        self.assertDictEqual({'error': {'type': "InternalServerError", "message": InternalServerError.description}},
                             resp.get_json())
