"""Tests for execution cancel endpoint."""
import json
from unittest import TestCase

from dimensigon.domain.entities import User, Orchestration, OrchExecution
from dimensigon.web import create_app, db


class TestCancelExecution(TestCase):

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create operator user
        self.user = User(
            id='00000000-0000-0000-0000-000000000099',
            name='testop', groups=['operator'], active=True
        )
        self.user.set_password('pass')
        db.session.add(self.user)

        # Create a running orchestration execution
        orch = Orchestration(name='test-orch', version=1)
        db.session.add(orch)
        db.session.flush()

        from dimensigon.utils.helpers import get_now
        self.exec = OrchExecution(
            id='00000000-0000-0000-0000-eeeeeeeeee01',
            orchestration_id=orch.id,
            start_time=get_now(),
        )
        db.session.add(self.exec)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        return self.client.post(
            '/dm-webmanager/login',
            data=json.dumps({'username': 'testop', 'password': 'pass'}),
            content_type='application/json'
        )

    def test_cancel_running_execution(self):
        """Cancel a running execution returns 200."""
        self._login()
        resp = self.client.post(f'/dm-webmanager/executions/{self.exec.id}/cancel')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('Cancellation requested', data['message'])

    def test_cancel_without_auth(self):
        """Cancel without auth redirects to login."""
        resp = self.client.post(
            f'/dm-webmanager/executions/{self.exec.id}/cancel',
            follow_redirects=False
        )
        self.assertEqual(302, resp.status_code)

    def test_cancel_nonexistent_execution(self):
        """Cancel nonexistent execution returns 404."""
        self._login()
        resp = self.client.post('/dm-webmanager/executions/nonexistent/cancel')
        self.assertEqual(404, resp.status_code)
