from unittest import TestCase
from unittest.mock import patch

from dimensigon import defaults
from dimensigon.domain.entities import Server
from dimensigon.web import create_app, db


class TestServer(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_create_server(self):
        s = Server('test')
        self.assertEqual(0, len(s.gates))

        s = Server('test', dns_or_ip='dns')
        self.assertEqual(1, len(s.gates))
        self.assertIsNone(s.gates[0].ip)
        self.assertEqual('dns', s.gates[0].dns)
        self.assertEqual(defaults.DEFAULT_PORT, s.gates[0].port)

        s = Server('test', port=5000)
        self.assertEqual(1, len(s.gates))
        self.assertIsNone(s.gates[0].ip)
        self.assertEqual('test', s.gates[0].dns)
        self.assertEqual(5000, s.gates[0].port)

        s = Server('test', dns_or_ip='dns', port=5000)
        self.assertEqual(1, len(s.gates))
        self.assertIsNone(s.gates[0].ip)
        self.assertEqual('dns', s.gates[0].dns)
        self.assertEqual(5000, s.gates[0].port)

        # create with gates
        s = Server('test', gates=[('gdns', 6000)])
        self.assertEqual(1, len(s.gates))
        self.assertIsNone(s.gates[0].ip)
        self.assertEqual('gdns', s.gates[0].dns)
        self.assertEqual(6000, s.gates[0].port)

        s = Server('test', dns_or_ip='dns', gates=[('gdns', 6000)])
        self.assertEqual(2, len(s.gates))
        self.assertIsNone(s.gates[0].ip)
        self.assertEqual('dns', s.gates[0].dns)
        self.assertEqual(defaults.DEFAULT_PORT, s.gates[0].port)
        self.assertIsNone(s.gates[1].ip)
        self.assertEqual('gdns', s.gates[1].dns)
        self.assertEqual(6000, s.gates[1].port)

        s = Server('test', port=5000, gates=[('gdns', 6000)])
        self.assertEqual(2, len(s.gates))
        self.assertIsNone(s.gates[0].ip)
        self.assertEqual('test', s.gates[0].dns)
        self.assertEqual(5000, s.gates[0].port)
        self.assertIsNone(s.gates[1].ip)
        self.assertEqual('gdns', s.gates[1].dns)
        self.assertEqual(6000, s.gates[1].port)

        s = Server('test', dns_or_ip='dns', port=5000, gates=[('gdns', 6000)])
        self.assertEqual(2, len(s.gates))
        self.assertIsNone(s.gates[0].ip)
        self.assertEqual('dns', s.gates[0].dns)
        self.assertEqual(5000, s.gates[0].port)
        self.assertIsNone(s.gates[1].ip)
        self.assertEqual('gdns', s.gates[1].dns)
        self.assertEqual(6000, s.gates[1].port)

    @patch('dimensigon.domain.entities.server.Gate')
    def test_create_server_dict_gate(self, mock_gate):
        dest = Server('dest', gates=[{'id': 1}])

        mock_gate.from_json.called_once_with({'id': 1})

    @patch('dimensigon.domain.entities.base.uuid.uuid4')
    def test_to_from_json(self, mock_uuid):
        mock_uuid.side_effect = ['22cd859d-ee91-4079-a112-000000000001',
                                 '22cd859d-ee91-4079-a112-000000000002',
                                 '22cd859d-ee91-4079-a112-000000000003']

        s = Server('server', dns_or_ip='dns', gates=[('gdns', 6000)])
        self.assertDictEqual({'id': '22cd859d-ee91-4079-a112-000000000001', 'name': 'server', 'granules': []},
                             s.to_json())
        db.session.add(s)
        db.session.commit()

        smashed = Server.from_json(s.to_json())

        self.assertIs(s, smashed)
        self.assertEqual(s.id, smashed.id)
        self.assertEqual(s.name, smashed.name)
        self.assertEqual(s.granules, smashed.granules)
        self.assertEqual(s.last_modified_at, smashed.last_modified_at)
