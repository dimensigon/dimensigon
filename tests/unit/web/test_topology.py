"""Tests for server topology API endpoint."""
import json
from unittest import TestCase

from dimensigon.domain.entities import User, Server, Gate, Route
from dimensigon.web import create_app, db


class TestTopology(TestCase):

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

        # Create test servers
        self.server1 = Server(
            id='00000000-0000-0000-0001-000000000001',
            name='node-local',
            dns_or_ip='10.0.0.1',
            port=20194,
            me=True,
        )
        self.server2 = Server(
            id='00000000-0000-0000-0001-000000000002',
            name='node-remote',
            dns_or_ip='10.0.0.2',
            port=20194,
        )
        db.session.add_all([self.server1, self.server2])
        db.session.flush()

        # Create a route: server2 is reachable via its own gate (neighbour, cost 0)
        gate2 = self.server2.gates[0]
        self.route = Route(destination=self.server2, proxy_server_or_gate=gate2, cost=0)
        db.session.add(self.route)
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

    def test_topology_returns_200_with_nodes_and_edges(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/topology')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('nodes', data)
        self.assertIn('edges', data)
        self.assertEqual(2, len(data['nodes']))
        self.assertEqual(1, len(data['edges']))

    def test_topology_node_fields(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/topology')
        data = resp.get_json()
        node_names = {n['name'] for n in data['nodes']}
        self.assertIn('node-local', node_names)
        self.assertIn('node-remote', node_names)

        local_node = next(n for n in data['nodes'] if n['name'] == 'node-local')
        self.assertTrue(local_node['me'])
        self.assertIsInstance(local_node['gates'], list)
        self.assertGreater(len(local_node['gates']), 0)
        self.assertIn('port', local_node['gates'][0])

    def test_topology_edge_fields(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/topology')
        data = resp.get_json()
        edge = data['edges'][0]
        self.assertEqual(str(self.server2.id), edge['destination_id'])
        self.assertEqual(0, edge['cost'])

    def test_topology_requires_auth(self):
        resp = self.client.get('/dm-webmanager/api/topology')
        # Should redirect or return 401/302 when not authenticated
        self.assertIn(resp.status_code, [302, 401, 422])
