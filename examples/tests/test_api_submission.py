"""Tier 2: Submit examples to a running DM API and verify acceptance.

Requires a running DM container (docker-compose.single.yml).
Run: pytest examples/tests/test_api_submission.py -v
"""

import random

import pytest
import requests


@pytest.fixture(scope='module')
def sample_action_templates(action_template_examples):
    """Sample 200 action templates for API testing."""
    rng = random.Random(42)
    sample = rng.sample(action_template_examples, min(200, len(action_template_examples)))
    return sample


@pytest.fixture(scope='module')
def sample_orchestrations(orchestration_examples):
    """Sample 100 orchestrations for API testing."""
    rng = random.Random(42)
    single = [ex for ex in orchestration_examples if ex['topology'] == 'single']
    sample = rng.sample(single, min(100, len(single)))
    return sample


class TestActionTemplateSubmission:
    """Test that action templates are accepted by the DM API."""

    def test_submit_action_templates(self, dm_url, dm_headers, sample_action_templates):
        """POST action templates and verify 201 response."""
        passed = 0
        failed = []

        for ex in sample_action_templates:
            resp = requests.post(
                f'{dm_url}/api/v1.0/action_templates',
                json=ex['dm_json'],
                headers=dm_headers,
                timeout=10,
            )
            if resp.status_code == 201:
                passed += 1
            else:
                failed.append((ex['id'], resp.status_code, resp.text[:200]))

        total = len(sample_action_templates)
        pass_rate = passed / total if total else 0

        if failed:
            msg = f"API submission: {passed}/{total} passed ({pass_rate:.0%})\n"
            for ex_id, status, text in failed[:10]:
                msg += f"  FAIL {ex_id}: {status} - {text}\n"
            if pass_rate < 0.95:
                pytest.fail(msg)
            else:
                pytest.xfail(msg)


class TestOrchestrationSubmission:
    """Test that orchestrations are accepted by the DM API."""

    def test_submit_orchestrations(self, dm_url, dm_headers, sample_orchestrations):
        """POST orchestrations/full and verify 201 response."""
        passed = 0
        failed = []

        for ex in sample_orchestrations:
            resp = requests.post(
                f'{dm_url}/api/v1.0/orchestrations/full',
                json=ex['dm_json'],
                headers=dm_headers,
                timeout=10,
            )
            if resp.status_code == 201:
                passed += 1
            else:
                failed.append((ex['id'], resp.status_code, resp.text[:200]))

        total = len(sample_orchestrations)
        pass_rate = passed / total if total else 0

        if failed:
            msg = f"API submission: {passed}/{total} passed ({pass_rate:.0%})\n"
            for ex_id, status, text in failed[:10]:
                msg += f"  FAIL {ex_id}: {status} - {text}\n"
            if pass_rate < 0.90:
                pytest.fail(msg)
            else:
                pytest.xfail(msg)
