"""Tests for DM-WebManager authentication flow."""
import json
from unittest import TestCase

from dimensigon.domain.entities import User
from dimensigon.web import create_app, db


class TestWebManagerAuth(TestCase):

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

        self.inactive_user = User(
            id='00000000-0000-0000-0000-000000000097',
            name='inactive', groups=['administrator'], active=False
        )
        self.inactive_user.set_password('inactivepass')

        db.session.add_all([self.admin_user, self.viewer_user, self.inactive_user])
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

    # --- Login tests ---

    def test_login_page_returns_200(self):
        """GET /dm-webmanager/login renders login page."""
        resp = self.client.get('/dm-webmanager/login')
        self.assertEqual(200, resp.status_code)
        self.assertIn(b'DM-WebManager', resp.data)

    def test_login_success(self):
        """Valid credentials return 200 and set cookies."""
        resp = self._login('testadmin', 'adminpass')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('Login successful', data['message'])
        self.assertEqual('testadmin', data['user']['name'])
        # Check cookies are set in response headers
        set_cookie_headers = resp.headers.getlist('Set-Cookie')
        cookie_names = [h.split('=')[0] for h in set_cookie_headers]
        self.assertIn('access_token_cookie', cookie_names)

    def test_login_bad_password(self):
        """Wrong password returns 401."""
        resp = self._login('testadmin', 'wrongpass')
        self.assertEqual(401, resp.status_code)

    def test_login_bad_username(self):
        """Non-existent user returns 401."""
        resp = self._login('nobody', 'pass')
        self.assertEqual(401, resp.status_code)

    def test_login_inactive_user(self):
        """Inactive user returns 403."""
        resp = self._login('inactive', 'inactivepass')
        self.assertEqual(403, resp.status_code)

    # --- Protected routes ---

    def test_dashboard_redirects_without_auth(self):
        """Unauthenticated access to dashboard redirects to login."""
        resp = self.client.get('/dm-webmanager/', follow_redirects=False)
        self.assertEqual(302, resp.status_code)
        self.assertIn('/login', resp.headers['Location'])

    def test_dashboard_accessible_after_login(self):
        """Dashboard accessible after login (cookies sent automatically)."""
        self._login('testadmin', 'adminpass')
        resp = self.client.get('/dm-webmanager/')
        self.assertEqual(200, resp.status_code)

    # --- Token refresh ---

    def test_refresh_token(self):
        """Token refresh returns new access token."""
        self._login('testadmin', 'adminpass')
        resp = self.client.post('/dm-webmanager/refresh')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('Token refreshed', data['message'])

    def test_refresh_without_login(self):
        """Refresh without login returns 401."""
        resp = self.client.post('/dm-webmanager/refresh')
        self.assertEqual(401, resp.status_code)

    # --- Logout ---

    def test_logout(self):
        """Logout clears cookies and blacklists token."""
        self._login('testadmin', 'adminpass')
        # Verify we can access dashboard
        resp = self.client.get('/dm-webmanager/')
        self.assertEqual(200, resp.status_code)

        # Logout
        resp = self.client.post('/dm-webmanager/logout')
        self.assertEqual(200, resp.status_code)

        # Dashboard should redirect to login now
        resp = self.client.get('/dm-webmanager/', follow_redirects=False)
        self.assertEqual(302, resp.status_code)

    # --- Role-based access ---

    def test_role_hierarchy(self):
        """Test role hierarchy calculation."""
        from dimensigon.web.admin.auth import get_user_role_level
        self.assertEqual(3, get_user_role_level(self.admin_user))
        self.assertEqual(1, get_user_role_level(self.viewer_user))
