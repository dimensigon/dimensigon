"""Tests for the AI chat endpoint in DM-WebManager."""
import json
import time
from unittest import TestCase
from unittest.mock import patch

from dimensigon.domain.entities import User
from dimensigon.web import create_app, db
from dimensigon.web.admin.routes import _ai_rate_limits


class TestAiChat(TestCase):

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create a test user
        self.user = User(
            id='00000000-0000-0000-0000-000000000050',
            name='aitester', groups=['administrator'], active=True
        )
        self.user.set_password('testpass')
        db.session.add(self.user)
        db.session.commit()

        # Clear rate limits between tests
        _ai_rate_limits.clear()

    def tearDown(self):
        _ai_rate_limits.clear()
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        return self.client.post(
            '/dm-webmanager/login',
            data=json.dumps({'username': 'aitester', 'password': 'testpass'}),
            content_type='application/json'
        )

    def _post_ai_chat(self, message='hello', mode='review', orchestration_context=None):
        payload = {'message': message, 'mode': mode}
        if orchestration_context is not None:
            payload['orchestration_context'] = orchestration_context
        return self.client.post(
            '/dm-webmanager/api/ai/chat',
            data=json.dumps(payload),
            content_type='application/json'
        )

    # --- Auth required ---

    def test_ai_chat_requires_auth(self):
        """POST /dm-webmanager/api/ai/chat without login returns 401."""
        resp = self._post_ai_chat()
        self.assertIn(resp.status_code, (401, 302, 422))

    # --- Mock response when AI is disabled ---

    def test_ai_chat_returns_200_when_ai_disabled(self):
        """POST /dm-webmanager/api/ai/chat returns 200 with mock response."""
        self._login()
        resp = self._post_ai_chat(message='Review my orchestration', mode='review')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('review', data['type'])
        self.assertIn('not currently configured', data['message'])
        self.assertIn('suggestions', data)

    def test_ai_chat_modify_mode_mock(self):
        """Modify mode returns mock response with modified_orchestration."""
        self._login()
        context = {'name': 'test-orch', 'steps': []}
        resp = self._post_ai_chat(message='Add a step', mode='modify', orchestration_context=context)
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('modify', data['type'])
        self.assertIn('not currently configured', data['message'])
        self.assertEqual(context, data['modified_orchestration'])

    # --- Validation ---

    def test_ai_chat_missing_message(self):
        """Empty message returns 400."""
        self._login()
        resp = self._post_ai_chat(message='')
        self.assertEqual(400, resp.status_code)

    def test_ai_chat_invalid_mode(self):
        """Invalid mode returns 400."""
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/ai/chat',
            data=json.dumps({'message': 'hello', 'mode': 'invalid'}),
            content_type='application/json'
        )
        self.assertEqual(400, resp.status_code)

    # --- Rate limiting ---

    def test_ai_chat_rate_limiting(self):
        """After 20 requests in an hour, the 21st returns 429."""
        self._login()

        # Make 20 requests successfully
        for i in range(20):
            resp = self._post_ai_chat(message=f'Request {i}')
            self.assertEqual(200, resp.status_code, f'Request {i} should succeed')

        # 21st request should be rate limited
        resp = self._post_ai_chat(message='One too many')
        self.assertEqual(429, resp.status_code)
        data = resp.get_json()
        self.assertIn('Rate limit exceeded', data['error'])

    def test_ai_chat_rate_limit_resets(self):
        """Rate limit window allows new requests after timestamps expire."""
        self._login()
        user_id = '00000000-0000-0000-0000-000000000050'

        # Manually fill the rate limit with old timestamps (>1 hour ago)
        old_time = time.time() - 3700
        _ai_rate_limits[user_id] = [old_time] * 20

        # Should still succeed because old entries are pruned
        resp = self._post_ai_chat(message='After window reset')
        self.assertEqual(200, resp.status_code)
