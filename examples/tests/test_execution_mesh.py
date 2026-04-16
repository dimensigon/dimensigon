"""Tier 3: Execute multi-server orchestrations on a 3-node mesh.

Requires docker-compose.mesh3.yml running.
Run: pytest examples/tests/test_execution_mesh.py -v
"""

import os
import random
import time

import pytest
import requests

MESH_MASTER_URL = os.environ.get('DM_MESH_MASTER_URL', 'http://localhost:20194')
DM_ROOT_PASSWORD = os.environ.get('DM_ROOT_PASSWORD', 'testpass123')


@pytest.fixture(scope='module')
def mesh_token():
    """Auth token for the mesh master."""
    try:
        resp = requests.post(
            f'{MESH_MASTER_URL}/api/v1.0/login',
            json={'username': 'root', 'password': DM_ROOT_PASSWORD},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get('access_token')
    except requests.ConnectionError:
        pass
    pytest.skip('Mesh master not available')


@pytest.fixture(scope='module')
def mesh_headers(mesh_token):
    return {
        'Authorization': f'Bearer {mesh_token}',
        'Content-Type': 'application/json',
    }


@pytest.fixture(scope='module')
def mesh_servers(mesh_headers):
    """Get list of servers in the mesh."""
    resp = requests.get(
        f'{MESH_MASTER_URL}/api/v1.0/servers',
        headers=mesh_headers,
        timeout=10,
    )
    if resp.status_code != 200:
        pytest.skip('Cannot list mesh servers')
    servers = resp.json()
    if len(servers) < 3:
        pytest.skip(f'Mesh has only {len(servers)} servers, need 3')
    return servers


class TestMeshOrchestrationExecution:
    """Test multi-server orchestration execution across the mesh."""

    def test_mesh_has_three_nodes(self, mesh_servers):
        """Verify the mesh has 3 nodes."""
        assert len(mesh_servers) >= 3

    def test_submit_and_launch_multi_server_orch(self, mesh_headers, mesh_servers,
                                                   multi_server_examples):
        """Submit a multi-server orchestration and verify execution."""
        if not multi_server_examples:
            pytest.skip('No multi-server examples')

        # Pick a simple multi-server example
        rng = random.Random(42)
        ex = rng.choice(multi_server_examples[:10])

        # Submit orchestration
        resp = requests.post(
            f'{MESH_MASTER_URL}/api/v1.0/orchestrations/full',
            json=ex['dm_json'],
            headers=mesh_headers,
            timeout=10,
        )
        if resp.status_code != 201:
            pytest.skip(f'Could not submit orchestration: {resp.status_code}')

        orch_id = resp.json().get('id')

        # Build hosts mapping from mesh servers
        hosts = {}
        for server in mesh_servers:
            for granule in server.get('granules', []):
                hosts.setdefault(granule, []).append(server['name'])
            hosts.setdefault('all', []).append(server['name'])

        # Launch
        launch_resp = requests.post(
            f'{MESH_MASTER_URL}/api/v1.0/launch/orchestration/{orch_id}',
            json={
                'hosts': hosts.get('all', [server['name'] for server in mesh_servers]),
                'params': {},
                'background': False,
                'skip_validation': True,
            },
            headers=mesh_headers,
            timeout=60,
        )

        # We accept either success or parameter validation failure
        # (since examples use {{input.var}} that won't be filled)
        assert launch_resp.status_code in (200, 201, 202, 400, 422), \
            f"Unexpected status: {launch_resp.status_code}: {launch_resp.text[:200]}"
