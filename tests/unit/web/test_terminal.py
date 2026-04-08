"""Tests for DShell Web Mode terminal sessions."""
import json
from unittest import TestCase

from dimensigon.domain.entities import User
from dimensigon.web import create_app, db
from dimensigon.web.admin.terminal import SessionManager, TerminalSession


class TestTerminalSession(TestCase):
    """Unit tests for TerminalSession command routing."""

    def setUp(self):
        self.session = TerminalSession('test-session-id', 'user-1')

    def test_help_command(self):
        output = self.session.execute('help')
        self.assertIn('Available commands', output)
        self.assertIn('help', output)
        self.assertIn('version', output)

    def test_version_command(self):
        output = self.session.execute('version')
        self.assertIn('DShell Web Mode', output)

    def test_whoami_command(self):
        output = self.session.execute('whoami')
        self.assertIn('user-1', output)

    def test_history_command(self):
        self.session.execute('help')
        self.session.execute('version')
        output = self.session.execute('history')
        self.assertIn('help', output)
        self.assertIn('version', output)
        self.assertIn('history', output)

    def test_unrecognized_command(self):
        output = self.session.execute('foobar')
        self.assertIn('Command not recognized', output)

    def test_get_history(self):
        self.session.execute('help')
        self.session.execute('version')
        history = self.session.get_history()
        self.assertEqual(['help', 'version'], history)

    def test_empty_history(self):
        output = self.session.execute('history')
        # 'history' itself is already in the list when history runs
        self.assertIn('history', output)

    def test_clear_command(self):
        self.session.execute('help')
        output = self.session.execute('clear')
        self.assertEqual('', output)


class TestSessionManager(TestCase):
    """Unit tests for SessionManager."""

    def setUp(self):
        self.manager = SessionManager()

    def test_create_session_returns_id(self):
        sid = self.manager.create_session('user-1')
        self.assertIsInstance(sid, str)
        self.assertTrue(len(sid) > 0)

    def test_get_session(self):
        sid = self.manager.create_session('user-1')
        session = self.manager.get_session(sid)
        self.assertIsNotNone(session)
        self.assertEqual(sid, session.session_id)
        self.assertEqual('user-1', session.user_id)

    def test_get_nonexistent_session(self):
        self.assertIsNone(self.manager.get_session('does-not-exist'))

    def test_close_session(self):
        sid = self.manager.create_session('user-1')
        self.manager.close_session(sid)
        self.assertIsNone(self.manager.get_session(sid))
        self.assertEqual(0, self.manager.active_sessions())

    def test_active_sessions(self):
        self.assertEqual(0, self.manager.active_sessions())
        self.manager.create_session('user-1')
        self.assertEqual(1, self.manager.active_sessions())
        self.manager.create_session('user-2')
        self.assertEqual(2, self.manager.active_sessions())

    def test_max_sessions_per_user(self):
        for _ in range(5):
            self.manager.create_session('user-1')
        with self.assertRaises(ValueError) as ctx:
            self.manager.create_session('user-1')
        self.assertIn('Maximum sessions', str(ctx.exception))

    def test_max_sessions_different_users(self):
        """Different users can each have their own sessions."""
        for _ in range(5):
            self.manager.create_session('user-1')
        # user-2 should still be able to create sessions
        sid = self.manager.create_session('user-2')
        self.assertIsNotNone(sid)

    def test_close_frees_slot(self):
        sids = []
        for _ in range(5):
            sids.append(self.manager.create_session('user-1'))
        self.manager.close_session(sids[0])
        # Should now be able to create one more
        new_sid = self.manager.create_session('user-1')
        self.assertIsNotNone(new_sid)


class TestTerminalAPI(TestCase):
    """Integration tests for terminal API endpoints."""

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.admin_user = User(
            id='00000000-0000-0000-0000-000000000099',
            name='testadmin', groups=['administrator'], active=True
        )
        self.admin_user.set_password('adminpass')
        db.session.add(self.admin_user)
        db.session.commit()

        # Reset the global session manager between tests
        from dimensigon.web.admin.terminal import session_manager
        session_manager._sessions.clear()
        session_manager._user_sessions.clear()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        return self.client.post(
            '/dm-webmanager/login',
            data=json.dumps({'username': 'testadmin', 'password': 'adminpass'}),
            content_type='application/json'
        )

    def _create_session(self):
        resp = self.client.post('/dm-webmanager/api/terminal/create')
        return resp

    def test_create_session_returns_session_id(self):
        self._login()
        resp = self._create_session()
        self.assertEqual(201, resp.status_code)
        data = resp.get_json()
        self.assertIn('session_id', data)
        self.assertTrue(len(data['session_id']) > 0)

    def test_execute_returns_output(self):
        self._login()
        resp = self._create_session()
        sid = resp.get_json()['session_id']

        resp = self.client.post(
            f'/dm-webmanager/api/terminal/{sid}/execute',
            data=json.dumps({'command': 'help'}),
            content_type='application/json'
        )
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('output', data)
        self.assertIn('Available commands', data['output'])

    def test_history_returns_past_commands(self):
        self._login()
        resp = self._create_session()
        sid = resp.get_json()['session_id']

        self.client.post(
            f'/dm-webmanager/api/terminal/{sid}/execute',
            data=json.dumps({'command': 'help'}),
            content_type='application/json'
        )
        self.client.post(
            f'/dm-webmanager/api/terminal/{sid}/execute',
            data=json.dumps({'command': 'version'}),
            content_type='application/json'
        )

        resp = self.client.get(f'/dm-webmanager/api/terminal/{sid}/history')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(['help', 'version'], data['history'])

    def test_close_session(self):
        self._login()
        resp = self._create_session()
        sid = resp.get_json()['session_id']

        resp = self.client.delete(f'/dm-webmanager/api/terminal/{sid}')
        self.assertEqual(200, resp.status_code)

        # Session should be gone
        resp = self.client.get(f'/dm-webmanager/api/terminal/{sid}/history')
        self.assertEqual(404, resp.status_code)

    def test_max_sessions_per_user(self):
        self._login()
        for _ in range(5):
            resp = self._create_session()
            self.assertEqual(201, resp.status_code)

        resp = self._create_session()
        self.assertEqual(429, resp.status_code)
        self.assertIn('Maximum sessions', resp.get_json()['error'])

    def test_unauthenticated_access_redirects(self):
        resp = self.client.post('/dm-webmanager/api/terminal/create')
        # webmanager_auth_required redirects to login
        self.assertEqual(302, resp.status_code)

    def test_execute_nonexistent_session(self):
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/terminal/fake-id/execute',
            data=json.dumps({'command': 'help'}),
            content_type='application/json'
        )
        self.assertEqual(404, resp.status_code)

    def test_execute_empty_command(self):
        self._login()
        resp = self._create_session()
        sid = resp.get_json()['session_id']

        resp = self.client.post(
            f'/dm-webmanager/api/terminal/{sid}/execute',
            data=json.dumps({'command': '   '}),
            content_type='application/json'
        )
        self.assertEqual(400, resp.status_code)
