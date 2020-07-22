from unittest import TestCase

from flask_jwt_extended import create_access_token

from dm.domain.entities import Log, Server
from dm.domain.entities.log import Mode
from dm.network.auth import HTTPBearerAuth
from dm.web import create_app, db


class TestLog(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
        db.create_all()
        self.src = Server('source', port=5000)
        self.dst = Server('destination', port=5000)

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_to_from_json(self):
        l = Log(source_server=self.src, target='/home/dimensigon/dimensigon/dm.log', destination_server=self.dst,
                dest_folder='/home/dimensigon/dimensigon-node3', id='11111111-2222-3333-4444-111111110001')

        self.src.id = '11111111-2222-3333-4444-555555550001'
        self.dst.id = '11111111-2222-3333-4444-555555550002'
        db.session.add(self.src)
        db.session.add(self.dst)

        l_json = l.to_json()
        self.assertDictEqual(
            dict(id='11111111-2222-3333-4444-111111110001',
                 src_server_id='11111111-2222-3333-4444-555555550001', target='/home/dimensigon/dimensigon/dm.log',
                 include=None,
                 exclude=None, dst_server_id='11111111-2222-3333-4444-555555550002',
                 dest_folder='/home/dimensigon/dimensigon-node3',
                 recursive=False,
                 mode='FOLDER',
                 deleted=False,
                 _old_target=None), l_json)

        smashed = Log.from_json(l_json)
        self.assertEqual(smashed.source_server, self.src)
        self.assertEqual(smashed.destination_server, self.dst)
        self.assertIsNone(smashed.include)
        self.assertIsNone(smashed.exclude)
        self.assertEqual(smashed.dest_folder, '/home/dimensigon/dimensigon-node3')
        self.assertEqual(smashed.target, '/home/dimensigon/dimensigon/dm.log')
        self.assertFalse(smashed.recursive)
        self.assertFalse(smashed.deleted)
        self.assertEqual(Mode.FOLDER, smashed.mode)
        self.assertIsNone(smashed._old_target)

        l_json = l.to_json(human=True)
        self.assertDictEqual(
            dict(id='11111111-2222-3333-4444-111111110001',
                 src_server=self.src.name, target='/home/dimensigon/dimensigon/dm.log',
                 include=None,
                 exclude=None, dst_server=self.dst.name,
                 dest_folder='/home/dimensigon/dimensigon-node3',
                 recursive=False,
                 mode='FOLDER',
                 deleted=False,
                 _old_target=None), l_json)

        l_json = l.to_json(human=True, delete_data=False)
        self.assertDictEqual(
            dict(id='11111111-2222-3333-4444-111111110001',
                 src_server=self.src.name, target='/home/dimensigon/dimensigon/dm.log',
                 include=None,
                 exclude=None, dst_server=self.dst.name,
                 dest_folder='/home/dimensigon/dimensigon-node3',
                 recursive=False,
                 mode='FOLDER'
                 ), l_json)

    def test_delete(self):
        l = Log(source_server=self.src, target='/home/dimensigon/dimensigon/dm.log', destination_server=self.dst,
                dest_folder='/home/dimensigon/dimensigon-node3', id='11111111-2222-3333-4444-111111110001')

        l.delete()

        self.assertEqual('/home/dimensigon/dimensigon/dm.log', l._old_target)
        self.assertNotEqual('/home/dimensigon/dimensigon/dm.log', l.target)
        self.assertTrue(l.deleted)

        db.session.add(l)
        db.session.commit()

        log_list = l.query.all()
        self.assertEqual(0, len(log_list))
        l = db.session.query(Log).filter(id='11111111-2222-3333-4444-111111110001').one()