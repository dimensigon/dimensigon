"""Tests for the /health endpoint."""
from unittest import TestCase

from dimensigon.web import create_app, db


class TestHealthEndpoint(TestCase):

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_health_returns_200(self):
        """Health endpoint returns 200 with no auth required."""
        resp = self.client.get('/health')
        self.assertEqual(200, resp.status_code)

    def test_health_json_payload(self):
        """Health endpoint returns expected JSON fields."""
        resp = self.client.get('/health')
        data = resp.get_json()
        self.assertIn('status', data)
        self.assertEqual('ok', data['status'])
        self.assertIn('version', data)
        self.assertIn('node', data)
        self.assertIn('neighbours', data)

    def test_health_trailing_slash(self):
        """Health endpoint works with trailing slash."""
        resp = self.client.get('/health/')
        self.assertEqual(200, resp.status_code)

    def test_health_detail(self):
        """Health endpoint with ?detail=true returns extended info."""
        resp = self.client.get('/health?detail=true')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('detail', data)
        detail = data['detail']
        self.assertIn('uptime_seconds', detail)
        self.assertIn('db_ok', detail)
        self.assertIn('memory_mb', detail)
        self.assertTrue(detail['db_ok'])

    def test_health_no_detail_by_default(self):
        """Health endpoint without ?detail=true omits detail section."""
        resp = self.client.get('/health')
        data = resp.get_json()
        self.assertNotIn('detail', data)
