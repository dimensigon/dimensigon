from flask import url_for
from werkzeug.exceptions import InternalServerError

from dimensigon.web import errors
from tests.base import TestDimensigonBase


class TestApi(TestDimensigonBase):

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
