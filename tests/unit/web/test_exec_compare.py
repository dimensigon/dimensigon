"""Tests for execution comparison and trends API endpoints."""
import json
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from dimensigon.domain.entities import (
    User, Orchestration, Step, ActionTemplate, ActionType,
    OrchExecution, StepExecution,
)
from dimensigon.web import create_app, db


class TestExecCompare(TestCase):

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
            name='testadmin', groups=['administrator'], active=True,
        )
        self.user.set_password('pass')
        db.session.add(self.user)

        # Create test action template
        self.at = ActionTemplate(
            id='00000000-0000-0000-000a-000000000011',
            name='Shell Command', version=1,
            action_type=ActionType.SHELL, code='echo hello',
        )
        db.session.add(self.at)

        # Create test orchestration
        self.orch = Orchestration(
            id='00000000-0000-0000-000b-000000000001',
            name='TestOrch', version=1,
        )
        db.session.add(self.orch)
        db.session.flush()

        # Create steps
        self.step1 = Step(
            id='00000000-0000-0000-000c-000000000001',
            orchestration=self.orch, undo=False,
            action_template=self.at,
        )
        self.step1.step_name = 'step-alpha'
        self.step2 = Step(
            id='00000000-0000-0000-000c-000000000002',
            orchestration=self.orch, undo=False,
            action_template=self.at,
        )
        self.step2.step_name = 'step-beta'
        db.session.add_all([self.step1, self.step2])
        db.session.flush()

        # Create two OrchExecutions
        now = datetime.now(timezone.utc)
        self.exec_a = OrchExecution(
            id='00000000-0000-0000-000d-000000000001',
            orchestration_id=str(self.orch.id),
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=2) + timedelta(seconds=30),
            success=True,
            params={'env': 'staging', 'retries': 3},
        )
        self.exec_b = OrchExecution(
            id='00000000-0000-0000-000d-000000000002',
            orchestration_id=str(self.orch.id),
            start_time=now - timedelta(hours=1),
            end_time=now - timedelta(hours=1) + timedelta(seconds=45),
            success=False,
            params={'env': 'production', 'retries': 3},
        )
        db.session.add_all([self.exec_a, self.exec_b])
        db.session.flush()

        # Create step executions for exec_a
        self.se_a1 = StepExecution(
            id='00000000-0000-0000-000e-000000000001',
            step_id=str(self.step1.id),
            orch_execution_id=str(self.exec_a.id),
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=2) + timedelta(seconds=10),
            success=True, rc=0,
        )
        self.se_a2 = StepExecution(
            id='00000000-0000-0000-000e-000000000002',
            step_id=str(self.step2.id),
            orch_execution_id=str(self.exec_a.id),
            start_time=now - timedelta(hours=2) + timedelta(seconds=10),
            end_time=now - timedelta(hours=2) + timedelta(seconds=25),
            success=True, rc=0,
        )
        # Create step executions for exec_b
        self.se_b1 = StepExecution(
            id='00000000-0000-0000-000e-000000000003',
            step_id=str(self.step1.id),
            orch_execution_id=str(self.exec_b.id),
            start_time=now - timedelta(hours=1),
            end_time=now - timedelta(hours=1) + timedelta(seconds=12),
            success=True, rc=0,
        )
        self.se_b2 = StepExecution(
            id='00000000-0000-0000-000e-000000000004',
            step_id=str(self.step2.id),
            orch_execution_id=str(self.exec_b.id),
            start_time=now - timedelta(hours=1) + timedelta(seconds=12),
            end_time=now - timedelta(hours=1) + timedelta(seconds=40),
            success=False, rc=1,
        )
        db.session.add_all([self.se_a1, self.se_a2, self.se_b1, self.se_b2])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        return self.client.post(
            '/dm-webmanager/login',
            data=json.dumps({'username': 'testadmin', 'password': 'pass'}),
            content_type='application/json',
        )

    # --- Compare endpoint ---

    def test_compare_returns_correct_diff_structure(self):
        self._login()
        resp = self.client.get(
            f'/dm-webmanager/api/executions/compare?a={self.exec_a.id}&b={self.exec_b.id}'
        )
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()

        # Top-level keys
        self.assertIn('execution_a', data)
        self.assertIn('execution_b', data)
        self.assertIn('diff', data)

        # Execution summaries
        ea = data['execution_a']
        eb = data['execution_b']
        self.assertEqual(str(self.exec_a.id), ea['id'])
        self.assertEqual(str(self.exec_b.id), eb['id'])
        self.assertEqual('success', ea['status'])
        self.assertEqual('failed', eb['status'])
        self.assertEqual('TestOrch', ea['orchestration_name'])
        self.assertIsNotNone(ea['duration'])
        self.assertIsNotNone(eb['duration'])
        self.assertEqual(2, len(ea['steps']))
        self.assertEqual(2, len(eb['steps']))

        # Diff structure
        diff = data['diff']
        self.assertTrue(diff['status_changed'])

        # Param diff: 'env' differs, 'retries' is the same
        self.assertIn('env', diff['param_diff'])
        self.assertEqual('staging', diff['param_diff']['env']['a'])
        self.assertEqual('production', diff['param_diff']['env']['b'])
        self.assertNotIn('retries', diff['param_diff'])

        # Step diffs
        self.assertEqual(2, len(diff['step_diffs']))
        step_names = [sd['step_name'] for sd in diff['step_diffs']]
        self.assertIn('step-alpha', step_names)
        self.assertIn('step-beta', step_names)

        # step-beta changed (success -> failed)
        beta_diff = next(sd for sd in diff['step_diffs'] if sd['step_name'] == 'step-beta')
        self.assertEqual('success', beta_diff['status_a'])
        self.assertEqual('failed', beta_diff['status_b'])
        self.assertTrue(beta_diff['changed'])

    def test_compare_missing_params_returns_400(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/executions/compare')
        self.assertEqual(400, resp.status_code)

    def test_compare_with_invalid_ids_returns_404(self):
        self._login()
        fake_id = '00000000-0000-0000-0000-ffffffffffff'
        resp = self.client.get(
            f'/dm-webmanager/api/executions/compare?a={fake_id}&b={self.exec_b.id}'
        )
        self.assertEqual(404, resp.status_code)

        resp = self.client.get(
            f'/dm-webmanager/api/executions/compare?a={self.exec_a.id}&b={fake_id}'
        )
        self.assertEqual(404, resp.status_code)

    # --- Trends endpoint ---

    def test_trends_returns_run_data(self):
        self._login()
        resp = self.client.get(
            f'/dm-webmanager/api/executions/trends/{self.orch.id}'
        )
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('runs', data)
        self.assertEqual(2, len(data['runs']))

        # Runs should be ordered oldest first
        run0 = data['runs'][0]
        run1 = data['runs'][1]
        self.assertIn('id', run0)
        self.assertIn('start_time', run0)
        self.assertIn('duration', run0)
        self.assertIn('status', run0)
        # exec_a is older
        self.assertEqual(str(self.exec_a.id), run0['id'])
        self.assertEqual(str(self.exec_b.id), run1['id'])

    def test_trends_invalid_orchestration_returns_404(self):
        self._login()
        fake_id = '00000000-0000-0000-0000-ffffffffffff'
        resp = self.client.get(f'/dm-webmanager/api/executions/trends/{fake_id}')
        self.assertEqual(404, resp.status_code)

    def test_trends_empty_when_no_executions(self):
        self._login()
        # Create an orchestration with no executions
        empty_orch = Orchestration(
            id='00000000-0000-0000-000b-000000000099',
            name='EmptyOrch', version=1,
        )
        db.session.add(empty_orch)
        db.session.commit()

        resp = self.client.get(
            f'/dm-webmanager/api/executions/trends/{empty_orch.id}'
        )
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(0, len(data['runs']))
