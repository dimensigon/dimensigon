"""Tests for the training data feedback loop (Plan 20)."""
import json
import uuid
from unittest import TestCase

from dimensigon.domain.entities import User, Orchestration
from dimensigon.domain.entities.training_candidate import TrainingCandidate
from dimensigon.ai.feedback import (
    compute_quality_score, increment_success, get_review_queue,
    approve_candidate, reject_candidate, SUCCESS_THRESHOLD,
)
from dimensigon.web import create_app, db


class TestComputeQualityScore(TestCase):
    """Tests for compute_quality_score with various orchestration JSONs."""

    def test_empty_json_returns_zero(self):
        self.assertEqual(0.0, compute_quality_score({}))

    def test_none_returns_zero(self):
        self.assertEqual(0.0, compute_quality_score(None))

    def test_non_dict_returns_zero(self):
        self.assertEqual(0.0, compute_quality_score("not a dict"))

    def test_perfect_score(self):
        orch = {
            'description': 'Deploy the application with rollback support',
            'undo_on_error': True,
            'timeout': 300,
            'steps': [
                {'action': 'install', 'target': '{{server}}'},
                {'action': 'configure', 'target': '{{server}}'},
            ],
        }
        self.assertEqual(1.0, compute_quality_score(orch))

    def test_description_only(self):
        orch = {
            'description': 'A simple orchestration',
            'steps': [],
        }
        # description=0.2, steps empty (0 steps, not 1-20)=0
        self.assertEqual(0.2, compute_quality_score(orch))

    def test_steps_count_boundary_one(self):
        orch = {
            'steps': [{'action': 'run'}],
        }
        # Only reasonable step count = 0.2
        self.assertEqual(0.2, compute_quality_score(orch))

    def test_steps_count_boundary_twenty(self):
        orch = {
            'steps': [{'action': f'step_{i}'} for i in range(20)],
        }
        self.assertEqual(0.2, compute_quality_score(orch))

    def test_steps_count_over_twenty(self):
        orch = {
            'steps': [{'action': f'step_{i}'} for i in range(21)],
        }
        self.assertEqual(0.0, compute_quality_score(orch))

    def test_error_handling_and_timeout(self):
        orch = {
            'stop_on_error': True,
            'timeout': 60,
            'steps': [],
        }
        # error_handling=0.2, timeout=0.2
        self.assertEqual(0.4, compute_quality_score(orch))

    def test_variables_detected(self):
        orch = {
            'steps': [{'target': '{{host}}', 'command': 'echo {{name}}'}],
        }
        # variables=0.2, steps(1)=0.2
        self.assertEqual(0.4, compute_quality_score(orch))


class TestIncrementSuccess(TestCase):
    """Tests for increment_success promoting candidates at threshold."""

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create test orchestration
        self.orch_id = str(uuid.uuid4())
        orch = Orchestration(id=self.orch_id, name='Test Orch', version=1)
        db.session.add(orch)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_increment_returns_none_for_unknown(self):
        result = increment_success(str(uuid.uuid4()))
        self.assertIsNone(result)

    def test_increment_increases_count(self):
        candidate = TrainingCandidate(
            orchestration_id=self.orch_id,
            source='ai_generated',
            success_count=0,
            status='tracking',
        )
        db.session.add(candidate)
        db.session.commit()

        result = increment_success(self.orch_id)
        self.assertIsNotNone(result)
        self.assertEqual(1, result.success_count)
        self.assertEqual('tracking', result.status)

    def test_increment_promotes_at_threshold(self):
        candidate = TrainingCandidate(
            orchestration_id=self.orch_id,
            source='ai_generated',
            success_count=SUCCESS_THRESHOLD - 1,
            status='tracking',
        )
        db.session.add(candidate)
        db.session.commit()

        result = increment_success(self.orch_id)
        self.assertIsNotNone(result)
        self.assertEqual(SUCCESS_THRESHOLD, result.success_count)
        self.assertEqual('pending', result.status)

    def test_increment_ignores_non_tracking(self):
        candidate = TrainingCandidate(
            orchestration_id=self.orch_id,
            source='ai_generated',
            success_count=1,
            status='pending',
        )
        db.session.add(candidate)
        db.session.commit()

        result = increment_success(self.orch_id)
        self.assertIsNone(result)


class TestReviewQueue(TestCase):
    """Tests for get_review_queue returning pending candidates."""

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.orch_id = str(uuid.uuid4())
        orch = Orchestration(id=self.orch_id, name='Test Orch', version=1)
        db.session.add(orch)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_empty_queue(self):
        result = get_review_queue()
        self.assertEqual([], result)

    def test_returns_only_pending(self):
        # Add one tracking, one pending, one approved
        db.session.add(TrainingCandidate(
            orchestration_id=self.orch_id, status='tracking',
        ))
        db.session.add(TrainingCandidate(
            orchestration_id=self.orch_id, status='pending', success_count=3,
        ))
        db.session.add(TrainingCandidate(
            orchestration_id=self.orch_id, status='approved',
        ))
        db.session.commit()

        result = get_review_queue()
        self.assertEqual(1, len(result))
        self.assertEqual('pending', result[0]['status'])
        self.assertEqual('Test Orch', result[0]['orchestration_name'])


class TestApproveReject(TestCase):
    """Tests for approve_candidate and reject_candidate."""

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.orch_id = str(uuid.uuid4())
        orch = Orchestration(id=self.orch_id, name='Test Orch', version=1)
        db.session.add(orch)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_approve_sets_status_and_reviewer(self):
        candidate = TrainingCandidate(
            orchestration_id=self.orch_id, status='pending', success_count=3,
        )
        db.session.add(candidate)
        db.session.commit()
        cid = candidate.id

        result = approve_candidate(cid, 'admin_user')
        self.assertIsNotNone(result)
        self.assertEqual('approved', result.status)
        self.assertEqual('admin_user', result.reviewer)
        self.assertIsNotNone(result.reviewed_at)

    def test_approve_returns_none_for_non_pending(self):
        candidate = TrainingCandidate(
            orchestration_id=self.orch_id, status='tracking',
        )
        db.session.add(candidate)
        db.session.commit()

        result = approve_candidate(candidate.id, 'admin')
        self.assertIsNone(result)

    def test_reject_sets_status_and_reviewer(self):
        candidate = TrainingCandidate(
            orchestration_id=self.orch_id, status='pending', success_count=3,
        )
        db.session.add(candidate)
        db.session.commit()
        cid = candidate.id

        result = reject_candidate(cid, 'admin_user')
        self.assertIsNotNone(result)
        self.assertEqual('rejected', result.status)
        self.assertEqual('admin_user', result.reviewer)
        self.assertIsNotNone(result.reviewed_at)

    def test_reject_returns_none_for_nonexistent(self):
        result = reject_candidate(str(uuid.uuid4()), 'admin')
        self.assertIsNone(result)


class TestTrainingEndpoints(TestCase):
    """Tests for the training feedback API endpoints."""

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create admin user
        self.user = User(
            id='00000000-0000-0000-0000-000000000099',
            name='testadmin', groups=['administrator'], active=True,
        )
        self.user.set_password('pass')
        db.session.add(self.user)
        db.session.commit()

        # Create test orchestration
        self.orch_id = str(uuid.uuid4())
        orch = Orchestration(id=self.orch_id, name='Feedback Orch', version=1)
        db.session.add(orch)
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

    def test_queue_empty(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/training/queue')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual([], data['candidates'])

    def test_queue_returns_pending(self):
        self._login()
        db.session.add(TrainingCandidate(
            orchestration_id=self.orch_id, status='pending', success_count=3,
        ))
        db.session.commit()

        resp = self.client.get('/dm-webmanager/api/training/queue')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(1, len(data['candidates']))
        self.assertEqual('Feedback Orch', data['candidates'][0]['orchestration_name'])

    def test_approve_endpoint(self):
        self._login()
        candidate = TrainingCandidate(
            orchestration_id=self.orch_id, status='pending', success_count=3,
        )
        db.session.add(candidate)
        db.session.commit()
        cid = candidate.id

        resp = self.client.post(f'/dm-webmanager/api/training/{cid}/approve')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('approved', data['candidate']['status'])
        self.assertEqual('testadmin', data['candidate']['reviewer'])

    def test_reject_endpoint(self):
        self._login()
        candidate = TrainingCandidate(
            orchestration_id=self.orch_id, status='pending', success_count=3,
        )
        db.session.add(candidate)
        db.session.commit()
        cid = candidate.id

        resp = self.client.post(f'/dm-webmanager/api/training/{cid}/reject')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('rejected', data['candidate']['status'])

    def test_approve_not_found(self):
        self._login()
        fake_id = str(uuid.uuid4())
        resp = self.client.post(f'/dm-webmanager/api/training/{fake_id}/approve')
        self.assertEqual(404, resp.status_code)

    def test_queue_requires_auth(self):
        resp = self.client.get('/dm-webmanager/api/training/queue')
        # Should redirect to login or return unauthorized
        self.assertIn(resp.status_code, (302, 401, 422))
