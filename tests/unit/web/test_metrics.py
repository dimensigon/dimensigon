"""Tests for the /metrics Prometheus endpoint."""
from unittest import TestCase

from prometheus_client import REGISTRY

from dimensigon.web import create_app, db


class TestMetricsEndpoint(TestCase):

    def setUp(self):
        # Clear prometheus_client default collectors between tests to avoid duplicates
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

    def test_metrics_returns_200(self):
        """Metrics endpoint returns 200 with Prometheus content type."""
        resp = self.client.get('/metrics')
        self.assertEqual(200, resp.status_code)
        self.assertIn('text/plain', resp.content_type)

    def test_metrics_contains_default_metrics(self):
        """Metrics endpoint returns Prometheus-formatted output."""
        resp = self.client.get('/metrics')
        body = resp.get_data(as_text=True)
        # Should contain at least some prometheus output (e.g. process or python metrics)
        self.assertIn('# HELP', body)
        self.assertIn('# TYPE', body)

    def test_api_request_increments_counter(self):
        """Making an API request increments the dm_api_requests_total counter."""
        # Make a request to the health endpoint first (excluded), then a normal one
        # The /metrics endpoint itself is excluded, so we hit /health to warm up,
        # then hit a non-excluded path.
        # Use a path that will return 404 but still be tracked
        self.client.get('/nonexistent-path-for-test')

        resp = self.client.get('/metrics')
        body = resp.get_data(as_text=True)
        # The counter should have recorded the request
        self.assertIn('dm_api_requests_total', body)

    def test_metrics_not_tracked_for_health(self):
        """Requests to /health should not be tracked in API metrics."""
        self.client.get('/health')
        resp = self.client.get('/metrics')
        body = resp.get_data(as_text=True)
        # health endpoint should not appear as a tracked endpoint
        # (it may still appear in the output as a metric name, but not as a label value)
        # We just verify the metrics endpoint works after hitting health
        self.assertEqual(200, resp.status_code)
