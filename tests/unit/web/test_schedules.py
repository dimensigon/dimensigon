"""Tests for scheduled orchestrations (cron) feature."""
import json
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from dimensigon.domain.entities import User, Orchestration
from dimensigon.domain.entities.schedule import Schedule
from dimensigon.use_cases.scheduler import compute_next_run
from dimensigon.web import create_app, db


class TestComputeNextRun(TestCase):
    """Tests for the compute_next_run helper."""

    def test_returns_future_datetime(self):
        now = datetime.now(timezone.utc)
        result = compute_next_run('*/5 * * * *', after=now)
        self.assertGreater(result, now)

    def test_returns_timezone_aware(self):
        result = compute_next_run('0 * * * *')
        self.assertIsNotNone(result.tzinfo)

    def test_every_minute(self):
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run('* * * * *', after=base)
        expected = datetime(2026, 1, 1, 12, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(result, expected)

    def test_specific_hour(self):
        base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run('0 14 * * *', after=base)
        expected = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(result, expected)

    def test_after_defaults_to_now(self):
        """When after is None, should return a time in the future from now."""
        result = compute_next_run('0 0 * * *')
        self.assertGreater(result, datetime.now(timezone.utc))


class TestScheduleCRUD(TestCase):
    """Tests for schedule CRUD API endpoints."""

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

        # Create test orchestration
        self.orch = Orchestration(
            id='00000000-0000-0000-0001-000000000001',
            name='Deploy App', version=1,
        )
        db.session.add(self.orch)
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

    def _create_schedule(self, **overrides):
        payload = {
            'orchestration_id': '00000000-0000-0000-0001-000000000001',
            'cron_expr': '*/10 * * * *',
        }
        payload.update(overrides)
        return self.client.post(
            '/dm-webmanager/api/schedules',
            data=json.dumps(payload),
            content_type='application/json'
        )

    # --- List ---

    def test_list_schedules_empty(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/schedules')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(data['schedules'], [])

    def test_list_schedules_returns_items(self):
        self._login()
        self._create_schedule()
        resp = self.client.get('/dm-webmanager/api/schedules')
        data = resp.get_json()
        self.assertEqual(1, len(data['schedules']))
        self.assertEqual('Deploy App', data['schedules'][0]['orchestration_name'])

    # --- Create ---

    def test_create_schedule_success(self):
        self._login()
        resp = self._create_schedule()
        self.assertEqual(201, resp.status_code)
        data = resp.get_json()
        self.assertIn('schedule', data)
        self.assertIn('id', data['schedule'])
        self.assertIsNotNone(data['schedule']['next_run'])

    def test_create_schedule_missing_orchestration_id(self):
        self._login()
        resp = self._create_schedule(orchestration_id=None)
        self.assertEqual(400, resp.status_code)

    def test_create_schedule_missing_cron_expr(self):
        self._login()
        resp = self._create_schedule(cron_expr='')
        self.assertEqual(400, resp.status_code)

    def test_create_schedule_invalid_cron(self):
        self._login()
        resp = self._create_schedule(cron_expr='not a cron')
        self.assertEqual(400, resp.status_code)
        self.assertIn('Invalid cron', resp.get_json()['error'])

    def test_create_schedule_orchestration_not_found(self):
        self._login()
        resp = self._create_schedule(orchestration_id='00000000-0000-0000-0000-999999999999')
        self.assertEqual(404, resp.status_code)

    def test_create_schedule_invalid_missed_policy(self):
        self._login()
        resp = self._create_schedule(missed_policy='invalid')
        self.assertEqual(400, resp.status_code)

    # --- Update ---

    def test_update_schedule(self):
        self._login()
        create_resp = self._create_schedule()
        schedule_id = create_resp.get_json()['schedule']['id']

        resp = self.client.put(
            f'/dm-webmanager/api/schedules/{schedule_id}',
            data=json.dumps({'cron_expr': '0 0 * * *'}),
            content_type='application/json'
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual('0 0 * * *', resp.get_json()['schedule']['cron_expr'])

    def test_update_schedule_not_found(self):
        self._login()
        resp = self.client.put(
            '/dm-webmanager/api/schedules/00000000-0000-0000-0000-999999999999',
            data=json.dumps({'cron_expr': '0 0 * * *'}),
            content_type='application/json'
        )
        self.assertEqual(404, resp.status_code)

    def test_update_schedule_invalid_cron(self):
        self._login()
        create_resp = self._create_schedule()
        schedule_id = create_resp.get_json()['schedule']['id']

        resp = self.client.put(
            f'/dm-webmanager/api/schedules/{schedule_id}',
            data=json.dumps({'cron_expr': 'bad'}),
            content_type='application/json'
        )
        self.assertEqual(400, resp.status_code)

    # --- Delete ---

    def test_delete_schedule(self):
        self._login()
        create_resp = self._create_schedule()
        schedule_id = create_resp.get_json()['schedule']['id']

        resp = self.client.delete(f'/dm-webmanager/api/schedules/{schedule_id}')
        self.assertEqual(200, resp.status_code)

        # Verify gone
        list_resp = self.client.get('/dm-webmanager/api/schedules')
        self.assertEqual(0, len(list_resp.get_json()['schedules']))

    def test_delete_schedule_not_found(self):
        self._login()
        resp = self.client.delete('/dm-webmanager/api/schedules/00000000-0000-0000-0000-999999999999')
        self.assertEqual(404, resp.status_code)

    # --- Toggle ---

    def test_toggle_schedule(self):
        self._login()
        create_resp = self._create_schedule()
        schedule_id = create_resp.get_json()['schedule']['id']

        # Disable
        resp = self.client.patch(f'/dm-webmanager/api/schedules/{schedule_id}/toggle')
        self.assertEqual(200, resp.status_code)
        self.assertFalse(resp.get_json()['schedule']['enabled'])

        # Re-enable
        resp = self.client.patch(f'/dm-webmanager/api/schedules/{schedule_id}/toggle')
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.get_json()['schedule']['enabled'])
        self.assertIsNotNone(resp.get_json()['schedule']['next_run'])

    def test_toggle_not_found(self):
        self._login()
        resp = self.client.patch('/dm-webmanager/api/schedules/00000000-0000-0000-0000-999999999999/toggle')
        self.assertEqual(404, resp.status_code)

    # --- Auth required ---

    def test_schedules_require_auth(self):
        for url in ['/dm-webmanager/api/schedules']:
            resp = self.client.get(url)
            self.assertIn(resp.status_code, (401, 302, 422),
                          f'{url} should require auth, got {resp.status_code}')
