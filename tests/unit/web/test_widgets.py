"""Tests for dashboard widget API endpoints."""
import json
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from dimensigon.domain.entities import User, Orchestration, ActionTemplate, ActionType
from dimensigon.domain.entities import OrchExecution
from dimensigon.web import create_app, db


class TestWidgets(TestCase):

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create test user
        self.user = User(
            id='00000000-0000-0000-0000-000000000099',
            name='testadmin', groups=['administrator'], active=True
        )
        self.user.set_password('pass')
        db.session.add(self.user)

        # Create test orchestrations
        self.orch1 = Orchestration(
            id='00000000-0000-0000-0001-000000000001',
            name='Deploy App', version=1,
        )
        self.orch2 = Orchestration(
            id='00000000-0000-0000-0001-000000000002',
            name='Restart Service', version=1,
        )
        db.session.add_all([self.orch1, self.orch2])
        db.session.flush()

        # Create test executions across several days
        now = datetime.now(timezone.utc)
        self.executions = []
        for i in range(5):
            ex = OrchExecution(
                orchestration_id=self.orch1.id,
                start_time=now - timedelta(days=i),
                success=True if i % 2 == 0 else False,
            )
            self.executions.append(ex)
        # Add a couple for orch2 (all failed)
        for i in range(3):
            ex = OrchExecution(
                orchestration_id=self.orch2.id,
                start_time=now - timedelta(days=i, hours=1),
                success=False,
            )
            self.executions.append(ex)

        db.session.add_all(self.executions)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        return self.client.post(
            '/dm-webmanager/login',
            data=json.dumps({'username': 'testadmin', 'password': 'pass'}),
            content_type='application/json'
        )

    # --- Success Rate ---

    def test_success_rate_returns_200(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/widgets/success-rate')
        self.assertEqual(200, resp.status_code)

    def test_success_rate_structure(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/widgets/success-rate')
        data = resp.get_json()
        self.assertIn('days', data)
        self.assertEqual(7, len(data['days']))
        day = data['days'][0]
        self.assertIn('date', day)
        self.assertIn('total', day)
        self.assertIn('success', day)
        self.assertIn('rate', day)

    # --- Top Failures ---

    def test_top_failures_returns_200(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/widgets/top-failures')
        self.assertEqual(200, resp.status_code)

    def test_top_failures_structure(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/widgets/top-failures')
        data = resp.get_json()
        self.assertIn('failures', data)
        self.assertIsInstance(data['failures'], list)
        # We have failures for both orchestrations
        self.assertGreater(len(data['failures']), 0)
        entry = data['failures'][0]
        self.assertIn('name', entry)
        self.assertIn('count', entry)

    def test_top_failures_order(self):
        """Most failures should appear first."""
        self._login()
        resp = self.client.get('/dm-webmanager/api/widgets/top-failures')
        data = resp.get_json()
        failures = data['failures']
        # Restart Service has 3 failures, Deploy App has 2
        self.assertEqual('Restart Service', failures[0]['name'])

    # --- Recent Activity ---

    def test_recent_activity_returns_200(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/widgets/recent-activity')
        self.assertEqual(200, resp.status_code)

    def test_recent_activity_structure(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/widgets/recent-activity')
        data = resp.get_json()
        self.assertIn('events', data)
        self.assertIsInstance(data['events'], list)
        self.assertGreater(len(data['events']), 0)
        event = data['events'][0]
        self.assertIn('id', event)
        self.assertIn('orchestration_name', event)
        self.assertIn('status', event)
        self.assertIn('start_time', event)
        self.assertIn('server_name', event)

    def test_recent_activity_ordered_desc(self):
        """Most recent execution should come first."""
        self._login()
        resp = self.client.get('/dm-webmanager/api/widgets/recent-activity')
        data = resp.get_json()
        events = data['events']
        times = [e['start_time'] for e in events if e['start_time']]
        self.assertEqual(times, sorted(times, reverse=True))

    # --- Auth required ---

    def test_widgets_require_auth(self):
        """All widget endpoints should return 401/302 without auth."""
        for url in [
            '/dm-webmanager/api/widgets/success-rate',
            '/dm-webmanager/api/widgets/top-failures',
            '/dm-webmanager/api/widgets/recent-activity',
        ]:
            resp = self.client.get(url)
            self.assertIn(resp.status_code, (401, 302, 422),
                          f'{url} should require auth, got {resp.status_code}')
