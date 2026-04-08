"""Tests for audit log feature."""
import json
from unittest import TestCase

from dimensigon.domain.entities import User
from dimensigon.domain.entities.audit import AuditEntry
from dimensigon.web import create_app, db


class TestAuditLog(TestCase):

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create test users
        self.admin_user = User(
            id='00000000-0000-0000-0000-000000000099',
            name='testadmin', groups=['administrator'], active=True
        )
        self.admin_user.set_password('adminpass')

        self.viewer_user = User(
            id='00000000-0000-0000-0000-000000000098',
            name='testviewer', groups=['readonly'], active=True
        )
        self.viewer_user.set_password('viewerpass')

        db.session.add_all([self.admin_user, self.viewer_user])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self, username, password):
        return self.client.post(
            '/dm-webmanager/login',
            data=json.dumps({'username': username, 'password': password}),
            content_type='application/json'
        )

    # --- Tests ---

    def test_login_creates_audit_entry(self):
        """Successful login should create an audit entry with action='login'."""
        resp = self._login('testadmin', 'adminpass')
        self.assertEqual(200, resp.status_code)

        entries = db.session.execute(
            db.select(AuditEntry).where(AuditEntry.action == 'login')
        ).scalars().all()
        self.assertGreaterEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual('login', entry.action)
        self.assertIsNotNone(entry.timestamp)
        self.assertIsNotNone(entry.ip_address)

    def test_get_audit_returns_entries(self):
        """GET /dm-webmanager/api/audit returns audit entries for admins."""
        # Login to generate an audit entry
        self._login('testadmin', 'adminpass')

        # Now fetch audit log (admin is already logged in via cookies)
        resp = self.client.get('/dm-webmanager/api/audit')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('entries', data)
        self.assertIn('total', data)
        self.assertIn('page', data)
        self.assertIn('per_page', data)
        self.assertGreaterEqual(data['total'], 1)
        self.assertEqual(1, data['page'])

    def test_audit_log_requires_administrator(self):
        """Non-admin users should not be able to access the audit log."""
        self._login('testviewer', 'viewerpass')
        resp = self.client.get('/dm-webmanager/api/audit')
        self.assertEqual(403, resp.status_code)

    def test_audit_log_unauthenticated(self):
        """Unauthenticated access to audit log should be rejected."""
        resp = self.client.get('/dm-webmanager/api/audit')
        # Should redirect to login or return 401/302
        self.assertIn(resp.status_code, [302, 401])

    def test_audit_log_filter_by_action(self):
        """Audit log can be filtered by action."""
        self._login('testadmin', 'adminpass')

        resp = self.client.get('/dm-webmanager/api/audit?action=login')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        for entry in data['entries']:
            self.assertEqual('login', entry['action'])

    def test_audit_log_pagination(self):
        """Audit log supports pagination parameters."""
        self._login('testadmin', 'adminpass')

        resp = self.client.get('/dm-webmanager/api/audit?page=1&per_page=5')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(1, data['page'])
        self.assertEqual(5, data['per_page'])
