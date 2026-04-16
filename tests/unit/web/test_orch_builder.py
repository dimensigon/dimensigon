"""Tests for orchestration builder API endpoints."""
import json
from unittest import TestCase

from dimensigon.domain.entities import User, ActionTemplate, ActionType
from dimensigon.web import create_app, db


class TestOrchBuilder(TestCase):

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

        # Create test action templates
        self.at1 = ActionTemplate(
            id='00000000-0000-0000-000a-000000000011',
            name='Shell Command', version=1,
            action_type=ActionType.SHELL, code='echo hello'
        )
        self.at2 = ActionTemplate(
            id='00000000-0000-0000-000a-000000000012',
            name='File Transfer', version=1,
            action_type=ActionType.SHELL, code='scp file'
        )
        db.session.add_all([self.at1, self.at2])
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

    # --- Action Templates Palette ---

    def test_get_action_templates(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/builder/action-templates')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        # Response is a list or dict with action_templates key
        templates = data if isinstance(data, list) else data.get('action_templates', [])
        self.assertEqual(2, len(templates))

    # --- Validate ---

    def test_validate_valid_dag(self):
        self._login()
        payload = {
            'name': 'test',
            'steps': [
                {'id': 's1', 'action_template_id': str(self.at1.id), 'parents': [], 'children': ['s2']},
                {'id': 's2', 'action_template_id': str(self.at2.id), 'parents': ['s1'], 'children': []},
            ]
        }
        resp = self.client.post(
            '/dm-webmanager/api/builder/validate',
            data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.get_json()['valid'])

    def test_validate_cycle_detected(self):
        self._login()
        payload = {
            'name': 'test',
            'steps': [
                {'id': 's1', 'action_template_id': str(self.at1.id), 'parents': ['s2'], 'children': ['s2']},
                {'id': 's2', 'action_template_id': str(self.at2.id), 'parents': ['s1'], 'children': ['s1']},
            ]
        }
        resp = self.client.post(
            '/dm-webmanager/api/builder/validate',
            data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertFalse(data['valid'])
        self.assertTrue(any('cycle' in e.lower() for e in data['errors']))

    def test_validate_missing_action_template(self):
        self._login()
        payload = {
            'name': 'test',
            'steps': [
                {'id': 's1', 'parents': [], 'children': []},
            ]
        }
        resp = self.client.post(
            '/dm-webmanager/api/builder/validate',
            data=json.dumps(payload), content_type='application/json'
        )
        data = resp.get_json()
        self.assertFalse(data['valid'])

    # --- Save ---

    def test_save_orchestration(self):
        self._login()
        payload = {
            'name': 'My New Orch',
            'description': 'Built visually',
            'stop_on_error': True,
            'steps': [
                {'id': 's1', 'action_template_id': str(self.at1.id), 'target': ['server1'], 'parents': [], 'children': ['s2'], 'undo': False},
                {'id': 's2', 'action_template_id': str(self.at2.id), 'target': ['server2'], 'parents': ['s1'], 'children': [], 'undo': False},
            ]
        }
        resp = self.client.post(
            '/dm-webmanager/api/builder/save',
            data=json.dumps(payload), content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201])
        data = resp.get_json()
        # ID may be at top level or nested under 'orchestration'
        orch_id = data.get('id') or data.get('orchestration', {}).get('id')
        self.assertIsNotNone(orch_id)

    def test_save_without_name_fails(self):
        self._login()
        payload = {'name': '', 'steps': []}
        resp = self.client.post(
            '/dm-webmanager/api/builder/save',
            data=json.dumps(payload), content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 200])
        data = resp.get_json()
        self.assertTrue('error' in data or 'errors' in data)
