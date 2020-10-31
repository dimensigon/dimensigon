from unittest import TestCase

from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import Server
from dimensigon.domain.entities.file import File
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import create_app, db


class TestFile(TestCase):
    def setUp(self):
        self.maxDiff = None
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
        db.create_all()
        self.src = Server('source', port=5000, id='00000000-0000-0000-0000-000000000000')
        self.dst1 = Server('destination1', port=5000, id='00000000-0000-0000-0000-000000000001')
        self.dst2 = Server('destination2', port=5000, id='00000000-0000-0000-0000-000000000002')
        self.dst3 = Server('destination3', port=5000, id='00000000-0000-0000-0000-000000000003')
        db.session.add_all([self.src, self.dst1, self.dst2, self.dst3])

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_to_json(self):
        dst_servers = [self.dst1, (self.dst2, '/'), (self.dst3.id, '/')]
        f = File(source_server=self.src, target='/home/dimensigon/dimensigon/dimensigon.log',
                 destination_servers=dst_servers,
                 id='11111111-2222-3333-4444-111111110001')
        db.session.add(f)
        dst_servers = f.destinations

        f_json = f.to_json(destinations=True)

        self.assertDictEqual(
            dict(id='11111111-2222-3333-4444-111111110001',
                 src_server_id='00000000-0000-0000-0000-000000000000',
                 target='/home/dimensigon/dimensigon/dimensigon.log',
                 destinations=[{'dst_server_id': '00000000-0000-0000-0000-000000000001', 'dest_folder': None},
                               {'dst_server_id': '00000000-0000-0000-0000-000000000002', 'dest_folder': '/'},
                               {'dst_server_id': '00000000-0000-0000-0000-000000000003', 'dest_folder': '/'}],
                 dest_folder=None,
                 deleted=False,
                 _old_target=None), f_json)

        f_json = f.to_json()

        self.assertDictEqual(
            dict(id='11111111-2222-3333-4444-111111110001',
                 src_server_id='00000000-0000-0000-0000-000000000000',
                 target='/home/dimensigon/dimensigon/dimensigon.log',
                 dest_folder=None,
                 deleted=False,
                 _old_target=None), f_json)

        f_json = f.to_json(human=True, destinations=True, no_delete=True)

        self.assertDictEqual(
            dict(id='11111111-2222-3333-4444-111111110001',
                 src_server='source',
                 target='/home/dimensigon/dimensigon/dimensigon.log',
                 destinations=[{'dst_server': 'destination1', 'dest_folder': None},
                               {'dst_server': 'destination2', 'dest_folder': '/'},
                               {'dst_server': 'destination3', 'dest_folder': '/'}],
                 dest_folder=None), f_json)

    def test_from_json(self):
        dst_servers = [self.dst1, (self.dst2, '/'), (self.dst3.id, '/')]
        f = File(source_server=self.src, target='/home/dimensigon/dimensigon/dimensigon.log',
                 destination_servers=dst_servers,
                 id='11111111-2222-3333-4444-111111110001')
        dst_servers = f.destinations
        db.session.add(f)
        db.session.commit()
        db.session.close()

        smashed = File.from_json(dict(id='11111111-2222-3333-4444-111111110001',
                                      src_server_id='00000000-0000-0000-0000-000000000000',
                                      target='/home/dimensigon/dimensigon/dimensigon.log',
                                      dest_folder='/home/dimensigon',
                                      deleted=False,
                                      _old_target=None))
        self.assertEqual(smashed.source_server.id, '00000000-0000-0000-0000-000000000000')
        self.assertEqual(smashed.dest_folder, '/home/dimensigon')
        self.assertEqual(smashed.target, '/home/dimensigon/dimensigon/dimensigon.log')
        self.assertFalse(smashed.deleted)
        self.assertListEqual([('00000000-0000-0000-0000-000000000001', None),
                              ('00000000-0000-0000-0000-000000000002', '/'),
                              ('00000000-0000-0000-0000-000000000003', '/')],
                             [(d.destination_server.id, d.dest_folder) for d in smashed.destinations])
        self.assertIsNone(smashed._old_target)

    def test_delete(self):
        dst_servers = [self.dst1, (self.dst2, '/'), (self.dst3.id, '/')]
        f = File(source_server=self.src, target='/home/dimensigon/dimensigon/dimensigon.log',
                 destination_servers=dst_servers,
                 id='11111111-2222-3333-4444-111111110001')

        f.delete()

        self.assertEqual('/home/dimensigon/dimensigon/dimensigon.log', f._old_target)
        self.assertNotEqual('/home/dimensigon/dimensigon/dimensigon.log', f.target)
        self.assertTrue(f.deleted)

        db.session.add(f)
        db.session.commit()

        log_list = f.query.all()
        self.assertEqual(0, len(log_list))
        f = db.session.query(File).filter_by(id='11111111-2222-3333-4444-111111110001').one()
        self.assertTrue(all([d.deleted for d in f.destinations]))

