import uuid
from unittest import TestCase
from flask_jwt_extended import create_access_token

from dm.domain.entities import Log, Server
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth


class TestServer(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('test'))
        db.create_all()
        self.src = Server('source', port=5000)
        self.dst = Server('destination', port=5000)

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_json(self):
        l = Log(source_server=self.src, target='/home/dimensigon/dimensigon/dm.log', destination_server=self.dst,
                dest_folder='/home/dimensigon/dimensigon-node3')

        with self.assertRaises(RuntimeError):
            l_json = l.to_json()

        self.src.id = uuid.UUID('11111111-2222-3333-4444-555555550001')
        self.dst.id = uuid.UUID('11111111-2222-3333-4444-555555550002')
        db.session.add(self.src)
        db.session.add(self.dst)

        l_json = l.to_json()
        self.assertDictEqual(
            dict(src_server_id='11111111-2222-3333-4444-555555550001', target='/home/dimensigon/dimensigon/dm.log',
                 include=None,
                 exclude=None, dst_server_id='11111111-2222-3333-4444-555555550002',
                 dest_folder='/home/dimensigon/dimensigon-node3',
                 recursive=False), l_json)

        smashed = Log.from_json(l_json)
        self.assertEqual(smashed.source_server, self.src)
        self.assertEqual(smashed.destination_server, self.dst)
        self.assertIsNone(smashed.include)
        self.assertIsNone(smashed.exclude)
        self.assertEqual(smashed.dest_folder, '/home/dimensigon/dimensigon-node3')
        self.assertEqual(smashed.target, '/home/dimensigon/dimensigon/dm.log')
        self.assertFalse(smashed.recursive)
