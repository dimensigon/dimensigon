from unittest import TestCase

from flask_jwt_extended import create_access_token
from sqlalchemy.orm.exc import NoResultFound

from dm.domain.entities import Gate, Server
from dm.web import create_app, db


class TestGate(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.headers = {"Authorization": f"Bearer {create_access_token('test')}"}

        db.create_all()
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_to_from_json(self):
        s = Server('test')
        g = Gate(server=s, dns='dns', port=8)

        g_json = g.to_json()
        self.assertEqual(g.dns, g_json['dns'])
        self.assertEqual(g.ip, g_json['ip'])
        self.assertEqual(g.port, g_json['port'])
        self.assertIsNone(g_json['server_id'])

        # set id to resolve server_id from gate object
        s = Server('test', id='aaaaaaaa-1234-5678-1234-56781234aaa1')
        g = Gate(server=s, dns='dns', port=8, id='aaaaaaaa-1234-5678-1234-56781234aaa2')

        g_json = g.to_json()
        self.assertDictEqual(
            {'server_id': 'aaaaaaaa-1234-5678-1234-56781234aaa1', 'dns': 'dns', 'ip': None, 'port': 8,
             'id': 'aaaaaaaa-1234-5678-1234-56781234aaa2'}, g_json)

        with self.assertRaises(NoResultFound):
            smashed = Gate.from_json(g_json)

        s = Server('test2', id='aaaaaaaa-1234-5678-1234-56781234aaa1')
        db.session.add(s)

        g_smashed = Gate.from_json(g_json)

        self.assertIsNot(g, g_smashed)
        self.assertEqual(g.dns, g_smashed.dns)
        self.assertEqual(g.ip, g_smashed.ip)
        self.assertEqual(g.port, g_smashed.port)
        self.assertIs(s, g_smashed.server)

        db.session.add(g_smashed)
        db.session.commit()

        g_json = g.to_json()

        self.assertEqual(
            {'id': 'aaaaaaaa-1234-5678-1234-56781234aaa2', 'server_id': 'aaaaaaaa-1234-5678-1234-56781234aaa1',
             'dns': 'dns', 'ip': None, 'port': 8}, g_json)

        # check from_json when persisted in database
        smashed = Gate.from_json(g_json)

        self.assertIs(g_smashed, smashed)
        self.assertEqual(g_smashed.server, smashed.server)
        self.assertEqual(g_smashed.dns, smashed.dns)
        self.assertEqual(g_smashed.ip, smashed.ip)
        self.assertEqual(g_smashed.port, smashed.port)
