"""Tests for orchestration versioning and rollback API endpoints."""
import json
from unittest import TestCase

from dimensigon.domain.entities import User, ActionTemplate, ActionType, Orchestration, Step
from dimensigon.domain.entities.orch_version import OrchestrationVersion
from dimensigon.web import create_app, db


class TestOrchVersioning(TestCase):

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create test user (operator role for rollback)
        self.user = User(
            id='00000000-0000-0000-0000-000000000099',
            name='testadmin', groups=['operator'], active=True
        )
        self.user.set_password('pass')
        db.session.add(self.user)

        # Create action template
        self.at1 = ActionTemplate(
            id='00000000-0000-0000-000a-000000000011',
            name='Shell Command', version=1,
            action_type=ActionType.SHELL, code='echo hello'
        )
        db.session.add(self.at1)
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

    def _save_orchestration(self, name='Test Orch', description='desc', message=None):
        """Helper to save an orchestration via builder endpoint."""
        payload = {
            'name': name,
            'description': description,
            'steps': [
                {
                    'id': 's1',
                    'action_template_id': str(self.at1.id),
                    'target': ['server1'],
                    'parents': [],
                    'children': [],
                    'undo': False,
                },
            ],
        }
        if message:
            payload['message'] = message
        resp = self.client.post(
            '/dm-webmanager/api/builder/save',
            data=json.dumps(payload),
            content_type='application/json'
        )
        return resp

    # --- Test: version list returns versions ---

    def test_list_versions(self):
        self._login()
        resp = self._save_orchestration(message='initial save')
        self.assertIn(resp.status_code, [200, 201])
        orch_id = resp.get_json()['orchestration']['id']

        resp = self.client.get(f'/dm-webmanager/api/orchestrations/{orch_id}/versions')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('versions', data)
        self.assertEqual(1, len(data['versions']))
        self.assertEqual(1, data['versions'][0]['version_number'])
        self.assertEqual('initial save', data['versions'][0]['message'])

    def test_list_versions_orch_not_found(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/orchestrations/00000000-0000-0000-0000-000000000000/versions')
        self.assertEqual(404, resp.status_code)

    # --- Test: diff between versions ---

    def test_diff_versions(self):
        self._login()
        # Save first version
        resp1 = self._save_orchestration(name='DiffOrch', description='version one')
        orch_id = resp1.get_json()['orchestration']['id']

        # Manually create a second version with different snapshot
        from dimensigon.utils.helpers import get_now
        v2 = OrchestrationVersion(
            orchestration_id=orch_id,
            version_number=2,
            json_snapshot={
                'id': orch_id,
                'name': 'DiffOrch',
                'version': 2,
                'description': 'version two',
                'stop_on_error': True,
                'stop_undo_on_error': True,
                'undo_on_error': True,
                'steps': [
                    {
                        'id': 'new-step',
                        'undo': False,
                        'action_template_id': str(self.at1.id),
                        'action_type': 'SHELL',
                        'target': ['server2'],
                        'parent_step_ids': [],
                        'children_step_ids': [],
                    }
                ],
            },
            author='tester',
            message='second version',
            created_at=get_now(),
        )
        db.session.add(v2)
        db.session.commit()

        resp = self.client.get(f'/dm-webmanager/api/orchestrations/{orch_id}/versions/1/diff/2')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('added', data)
        self.assertIn('removed', data)
        self.assertIn('changed', data)
        # v1 has the auto-created step, v2 has 'new-step' - they differ
        # The original step from v1 should be in removed, new-step in added
        self.assertTrue(len(data['added']) > 0 or len(data['removed']) > 0 or len(data['changed']) > 0)

    def test_diff_version_not_found(self):
        self._login()
        resp = self._save_orchestration(name='DiffOrch2')
        orch_id = resp.get_json()['orchestration']['id']

        resp = self.client.get(f'/dm-webmanager/api/orchestrations/{orch_id}/versions/1/diff/99')
        self.assertEqual(404, resp.status_code)

    # --- Test: rollback creates new version ---

    def test_rollback_creates_new_version(self):
        self._login()
        resp = self._save_orchestration(name='RollbackOrch', description='original')
        orch_id = resp.get_json()['orchestration']['id']

        # Verify we have version 1
        versions_resp = self.client.get(f'/dm-webmanager/api/orchestrations/{orch_id}/versions')
        self.assertEqual(1, len(versions_resp.get_json()['versions']))

        # Rollback to version 1 (creates version 2)
        rollback_resp = self.client.post(
            f'/dm-webmanager/api/orchestrations/{orch_id}/rollback/1'
        )
        self.assertEqual(200, rollback_resp.status_code)
        data = rollback_resp.get_json()
        self.assertIn('new_version_number', data)
        self.assertEqual(2, data['new_version_number'])

        # Verify version list now has 2 entries
        versions_resp = self.client.get(f'/dm-webmanager/api/orchestrations/{orch_id}/versions')
        versions = versions_resp.get_json()['versions']
        self.assertEqual(2, len(versions))
        self.assertIn('Rollback to version 1', versions[1]['message'])

    def test_rollback_version_not_found(self):
        self._login()
        resp = self._save_orchestration(name='RollbackOrch2')
        orch_id = resp.get_json()['orchestration']['id']

        rollback_resp = self.client.post(
            f'/dm-webmanager/api/orchestrations/{orch_id}/rollback/99'
        )
        self.assertEqual(404, rollback_resp.status_code)

    def test_rollback_orch_not_found(self):
        self._login()
        rollback_resp = self.client.post(
            '/dm-webmanager/api/orchestrations/00000000-0000-0000-0000-000000000000/rollback/1'
        )
        self.assertEqual(404, rollback_resp.status_code)

    # --- Test: auto-version on save ---

    def test_save_creates_version_automatically(self):
        self._login()
        resp = self._save_orchestration(name='AutoVer')
        self.assertIn(resp.status_code, [200, 201])
        orch_id = resp.get_json()['orchestration']['id']

        # Check that a version was auto-created
        versions = db.session.execute(
            db.select(OrchestrationVersion).filter_by(orchestration_id=orch_id)
        ).scalars().all()
        self.assertEqual(1, len(versions))
        self.assertEqual(1, versions[0].version_number)
        self.assertIsNotNone(versions[0].json_snapshot)
