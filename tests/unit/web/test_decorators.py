"""Regression tests for forward_or_dispatch decorator.

Ensures GET requests without JSON body don't raise 400/415 errors,
and POST requests with JSON body still work correctly.
"""
import json
from unittest import TestCase

from flask import Flask, g, jsonify

from dimensigon.web import db
from dimensigon.web.decorators import forward_or_dispatch, validate_schema


class TestForwardOrDispatch(TestCase):
    """Test that forward_or_dispatch handles missing JSON gracefully."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        self.app.config['TESTING'] = True
        db.init_app(self.app)

        @self.app.route('/test', methods=['GET', 'POST'])
        @forward_or_dispatch()
        def test_endpoint():
            return jsonify({'status': 'ok'})

        @self.app.before_request
        def set_server():
            from unittest.mock import MagicMock
            g.server = MagicMock()
            g.server.id = '00000000-0000-0000-0000-000000000001'

        self.client = self.app.test_client()

    def test_get_without_json_body(self):
        """GET request without JSON body should not raise 400/415."""
        with self.app.app_context():
            db.create_all()
            resp = self.client.get('/test')
            self.assertEqual(200, resp.status_code)
            self.assertEqual({'status': 'ok'}, resp.get_json())

    def test_post_with_json_body(self):
        """POST request with JSON body should work as before."""
        with self.app.app_context():
            db.create_all()
            resp = self.client.post('/test',
                                    data=json.dumps({'key': 'value'}),
                                    content_type='application/json')
            self.assertEqual(200, resp.status_code)
            self.assertEqual({'status': 'ok'}, resp.get_json())

    def test_post_without_content_type(self):
        """POST without Content-Type should not crash the decorator."""
        with self.app.app_context():
            db.create_all()
            resp = self.client.post('/test', data='not json')
            self.assertEqual(200, resp.status_code)


class TestValidateSchema(TestCase):
    """Test that validate_schema handles missing JSON gracefully."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        self.app.config['TESTING'] = True

        @self.app.route('/test', methods=['GET', 'POST'])
        @validate_schema()
        def test_endpoint():
            return jsonify({'status': 'ok'})

        self.client = self.app.test_client()

    def test_get_without_schema(self):
        """GET request without schema should pass through."""
        resp = self.client.get('/test')
        self.assertEqual(200, resp.status_code)
