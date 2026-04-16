"""Tests for federation peering endpoints."""
import json
from unittest import TestCase

from dimensigon.domain.entities import User
from dimensigon.domain.entities.federation import Peer, FederationLink
from dimensigon.web import create_app, db


class TestFederationEndpoints(TestCase):

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create admin user
        self.admin = User(
            id='00000000-0000-0000-0000-000000000099',
            name='testadmin', groups=['administrator'], active=True
        )
        self.admin.set_password('pass')
        db.session.add(self.admin)

        # Create non-admin user (viewer only)
        self.viewer = User(
            id='00000000-0000-0000-0000-000000000088',
            name='viewer', groups=['viewer'], active=True
        )
        self.viewer.set_password('pass')
        db.session.add(self.viewer)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self, username='testadmin', password='pass'):
        return self.client.post(
            '/dm-webmanager/login',
            data=json.dumps({'username': username, 'password': password}),
            content_type='application/json'
        )

    # --- List peers ---

    def test_list_peers_empty(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/federation/peers')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual([], data)

    def test_list_peers_with_data(self):
        self._login()
        # Create a peer via API
        self.client.post(
            '/dm-webmanager/api/federation/peers',
            data=json.dumps({'name': 'Peer A', 'endpoint': 'https://a.example.com/api'}),
            content_type='application/json',
        )
        resp = self.client.get('/dm-webmanager/api/federation/peers')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(1, len(data))
        self.assertEqual('Peer A', data[0]['name'])
        self.assertEqual('pending', data[0]['status'])

    # --- Initiate peering ---

    def test_initiate_peering(self):
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/federation/peers',
            data=json.dumps({'name': 'New Peer', 'endpoint': 'https://peer.example.com'}),
            content_type='application/json',
        )
        self.assertEqual(201, resp.status_code)
        data = resp.get_json()
        self.assertEqual('New Peer', data['name'])
        self.assertEqual('https://peer.example.com', data['endpoint'])
        self.assertEqual('pending', data['status'])
        self.assertIsNotNone(data['id'])

    def test_initiate_peering_missing_fields(self):
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/federation/peers',
            data=json.dumps({'name': 'No endpoint'}),
            content_type='application/json',
        )
        self.assertEqual(400, resp.status_code)

    # --- Accept peering ---

    def test_accept_peering(self):
        self._login()
        # Create peer
        resp = self.client.post(
            '/dm-webmanager/api/federation/peers',
            data=json.dumps({'name': 'To Accept', 'endpoint': 'https://accept.example.com'}),
            content_type='application/json',
        )
        peer_id = resp.get_json()['id']

        # Accept
        resp = self.client.post(f'/dm-webmanager/api/federation/peers/{peer_id}/accept')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('connected', data['status'])

    # --- Revoke peering ---

    def test_revoke_peering(self):
        self._login()
        # Create peer
        resp = self.client.post(
            '/dm-webmanager/api/federation/peers',
            data=json.dumps({'name': 'To Revoke', 'endpoint': 'https://revoke.example.com'}),
            content_type='application/json',
        )
        peer_id = resp.get_json()['id']

        # Revoke
        resp = self.client.post(f'/dm-webmanager/api/federation/peers/{peer_id}/revoke')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('revoked', data['status'])

    def test_revoke_deactivates_links(self):
        self._login()
        # Create peer
        resp = self.client.post(
            '/dm-webmanager/api/federation/peers',
            data=json.dumps({'name': 'Linked Peer', 'endpoint': 'https://link.example.com'}),
            content_type='application/json',
        )
        peer_id = resp.get_json()['id']

        # Add a federation link directly
        link = FederationLink(peer_id=peer_id, link_type='execution', active=True)
        db.session.add(link)
        db.session.commit()

        # Revoke peer
        self.client.post(f'/dm-webmanager/api/federation/peers/{peer_id}/revoke')

        # Verify link was deactivated
        updated_link = db.session.get(FederationLink, link.id)
        self.assertFalse(updated_link.active)

    # --- Role protection ---

    def test_requires_administrator_role(self):
        """Non-administrator users should be rejected for write operations."""
        self._login(username='viewer', password='pass')

        resp = self.client.post(
            '/dm-webmanager/api/federation/peers',
            data=json.dumps({'name': 'Test', 'endpoint': 'https://example.com'}),
            content_type='application/json',
        )
        self.assertEqual(403, resp.status_code)

    # --- Peer detail ---

    def test_get_peer_detail(self):
        self._login()
        # Create peer
        resp = self.client.post(
            '/dm-webmanager/api/federation/peers',
            data=json.dumps({'name': 'Detail Peer', 'endpoint': 'https://detail.example.com'}),
            content_type='application/json',
        )
        peer_id = resp.get_json()['id']

        resp = self.client.get(f'/dm-webmanager/api/federation/peers/{peer_id}')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('Detail Peer', data['name'])
        self.assertIn('links', data)
