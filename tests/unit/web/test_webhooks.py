"""Tests for webhook CRUD endpoints and dispatch_event function."""
import json
from unittest import TestCase
from unittest.mock import patch, MagicMock

from dimensigon.domain.entities import User
from dimensigon.domain.entities.webhook import Webhook, WebhookLog
from dimensigon.web import create_app, db


class TestWebhookCRUD(TestCase):

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

    # --- Create ---

    def test_create_webhook(self):
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/webhooks',
            data=json.dumps({
                'name': 'My Hook',
                'url': 'https://example.com/hook',
                'event_types': ['orchestration.completed'],
            }),
            content_type='application/json',
        )
        self.assertEqual(201, resp.status_code)
        data = resp.get_json()
        self.assertEqual('My Hook', data['name'])
        self.assertEqual('https://example.com/hook', data['url'])
        self.assertIn('orchestration.completed', data['event_types'])
        self.assertTrue(data['active'])
        self.assertIsNotNone(data['id'])

    def test_create_webhook_url_required(self):
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/webhooks',
            data=json.dumps({'name': 'No URL'}),
            content_type='application/json',
        )
        self.assertEqual(400, resp.status_code)

    # --- List ---

    def test_list_webhooks(self):
        self._login()
        # Create two webhooks
        for name in ('Hook A', 'Hook B'):
            self.client.post(
                '/dm-webmanager/api/webhooks',
                data=json.dumps({'name': name, 'url': 'https://example.com'}),
                content_type='application/json',
            )
        resp = self.client.get('/dm-webmanager/api/webhooks')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(2, len(data))

    # --- Delete ---

    def test_delete_webhook(self):
        self._login()
        # Create
        resp = self.client.post(
            '/dm-webmanager/api/webhooks',
            data=json.dumps({'name': 'To Delete', 'url': 'https://example.com'}),
            content_type='application/json',
        )
        webhook_id = resp.get_json()['id']

        # Delete
        resp = self.client.delete(f'/dm-webmanager/api/webhooks/{webhook_id}')
        self.assertEqual(200, resp.status_code)

        # Confirm gone
        resp = self.client.get('/dm-webmanager/api/webhooks')
        self.assertEqual(0, len(resp.get_json()))

    def test_delete_webhook_not_found(self):
        self._login()
        resp = self.client.delete('/dm-webmanager/api/webhooks/nonexistent-id')
        self.assertEqual(404, resp.status_code)

    # --- Update ---

    def test_update_webhook(self):
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/webhooks',
            data=json.dumps({'name': 'Original', 'url': 'https://example.com'}),
            content_type='application/json',
        )
        webhook_id = resp.get_json()['id']

        resp = self.client.put(
            f'/dm-webmanager/api/webhooks/{webhook_id}',
            data=json.dumps({'name': 'Updated', 'active': False}),
            content_type='application/json',
        )
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('Updated', data['name'])
        self.assertFalse(data['active'])

    # --- Auth required ---

    def test_webhooks_require_auth(self):
        resp = self.client.get('/dm-webmanager/api/webhooks')
        self.assertIn(resp.status_code, (401, 302, 422))


class TestDispatchEvent(TestCase):

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dimensigon.use_cases.webhooks.requests.post')
    @patch('dimensigon.use_cases.webhooks.threading.Thread')
    def test_dispatch_event_matches_webhooks(self, mock_thread_cls, mock_post):
        """dispatch_event should start a thread for each matching webhook."""
        # Create an active webhook matching the event type
        wh = Webhook(
            id='00000000-0000-0000-0000-000000000001',
            name='Test Hook',
            url='https://example.com/hook',
            event_types=['orchestration.completed'],
            active=True,
        )
        db.session.add(wh)
        db.session.commit()

        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        from dimensigon.use_cases.webhooks import dispatch_event
        dispatch_event('orchestration.completed', {'execution_id': '123'})

        mock_thread_cls.assert_called_once()
        mock_thread.start.assert_called_once()

    @patch('dimensigon.use_cases.webhooks.requests.post')
    @patch('dimensigon.use_cases.webhooks.threading.Thread')
    def test_dispatch_event_no_match(self, mock_thread_cls, mock_post):
        """dispatch_event should not start threads for non-matching webhooks."""
        wh = Webhook(
            id='00000000-0000-0000-0000-000000000002',
            name='Other Hook',
            url='https://example.com/hook',
            event_types=['orchestration.failed'],
            active=True,
        )
        db.session.add(wh)
        db.session.commit()

        from dimensigon.use_cases.webhooks import dispatch_event
        dispatch_event('orchestration.completed', {'execution_id': '123'})

        mock_thread_cls.assert_not_called()

    @patch('dimensigon.use_cases.webhooks.requests.post')
    def test_deliver_webhook_success(self, mock_post):
        """_deliver_webhook should log a successful delivery."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = 'OK'
        mock_post.return_value = mock_resp

        wh = Webhook(
            id='00000000-0000-0000-0000-000000000003',
            name='Deliver Hook',
            url='https://example.com/hook',
            event_types=['test.event'],
            active=True,
            retry_max=3,
        )
        db.session.add(wh)
        db.session.commit()

        from dimensigon.use_cases.webhooks import _deliver_webhook
        wh_data = {
            'id': wh.id,
            'url': wh.url,
            'headers': wh.headers,
            'retry_max': wh.retry_max,
        }
        _deliver_webhook(self.app, wh_data, 'test.event', {'msg': 'hello'})

        mock_post.assert_called_once()
        # Check that a log entry was created
        logs = db.session.execute(
            db.select(WebhookLog).where(WebhookLog.webhook_id == wh.id)
        ).scalars().all()
        self.assertEqual(1, len(logs))
        self.assertTrue(logs[0].success)
        self.assertEqual(200, logs[0].status_code)

    @patch('dimensigon.use_cases.webhooks.time.sleep')
    @patch('dimensigon.use_cases.webhooks.requests.post')
    def test_deliver_webhook_retries_on_failure(self, mock_post, mock_sleep):
        """_deliver_webhook should retry with backoff on failure."""
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.text = 'Internal Server Error'

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.text = 'OK'

        # Fail twice, then succeed
        mock_post.side_effect = [fail_resp, fail_resp, ok_resp]

        wh = Webhook(
            id='00000000-0000-0000-0000-000000000004',
            name='Retry Hook',
            url='https://example.com/hook',
            event_types=[],
            active=True,
            retry_max=5,
        )
        db.session.add(wh)
        db.session.commit()

        from dimensigon.use_cases.webhooks import _deliver_webhook
        wh_data = {
            'id': wh.id,
            'url': wh.url,
            'headers': wh.headers,
            'retry_max': wh.retry_max,
        }
        _deliver_webhook(self.app, wh_data, 'test.event', {'msg': 'retry'})

        self.assertEqual(3, mock_post.call_count)
        # Two backoff sleeps (1s, 2s)
        self.assertEqual(2, mock_sleep.call_count)
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

        logs = db.session.execute(
            db.select(WebhookLog).where(WebhookLog.webhook_id == wh.id)
        ).scalars().all()
        self.assertEqual(3, len(logs))
