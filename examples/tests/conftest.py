"""Shared pytest fixtures for DM container-based tests."""

import json
import os
import subprocess
import time

import pytest
import requests

DM_SINGLE_URL = os.environ.get('DM_TEST_URL', 'http://localhost:20194')
DM_MESH_MASTER_URL = os.environ.get('DM_MESH_MASTER_URL', 'http://localhost:20194')
DM_MESH_WEB_URL = os.environ.get('DM_MESH_WEB_URL', 'http://localhost:20195')
DM_MESH_DB_URL = os.environ.get('DM_MESH_DB_URL', 'http://localhost:20196')
DM_ROOT_PASSWORD = os.environ.get('DM_ROOT_PASSWORD', 'testpass123')


@pytest.fixture(scope='session')
def dm_auth_token():
    """Get a JWT auth token from the DM API."""
    try:
        resp = requests.post(
            f'{DM_SINGLE_URL}/api/v1.0/login',
            json={'username': 'root', 'password': DM_ROOT_PASSWORD},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get('access_token')
    except requests.ConnectionError:
        pass
    pytest.skip('DM server not available')


@pytest.fixture(scope='session')
def dm_headers(dm_auth_token):
    """Auth headers for DM API requests."""
    return {
        'Authorization': f'Bearer {dm_auth_token}',
        'Content-Type': 'application/json',
    }


@pytest.fixture(scope='session')
def dm_url():
    """DM server URL."""
    return DM_SINGLE_URL


@pytest.fixture(scope='session')
def all_examples():
    """Load all generated examples."""
    examples_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'output', 'all_examples.json'
    )
    if not os.path.exists(examples_path):
        pytest.skip('No examples generated. Run "python examples/generate.py generate" first.')

    with open(examples_path) as f:
        return json.load(f)


@pytest.fixture(scope='session')
def action_template_examples(all_examples):
    """Filter to action template examples only."""
    return [ex for ex in all_examples if ex['entity_type'] == 'action_template']


@pytest.fixture(scope='session')
def orchestration_examples(all_examples):
    """Filter to orchestration examples only."""
    return [ex for ex in all_examples if ex['entity_type'] == 'orchestration']


@pytest.fixture(scope='session')
def single_server_examples(orchestration_examples):
    """Filter to single-server orchestration examples."""
    return [ex for ex in orchestration_examples if ex['topology'] == 'single']


@pytest.fixture(scope='session')
def multi_server_examples(orchestration_examples):
    """Filter to multi-server orchestration examples."""
    return [ex for ex in orchestration_examples if ex['topology'] in ('multi', 'mesh')]
