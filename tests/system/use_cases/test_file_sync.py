import os
import time
from concurrent.futures.thread import ThreadPoolExecutor
from unittest import mock

import responses
from aioresponses import aioresponses
from pyfakefs.fake_filesystem_unittest import TestCase

from dimensigon.domain.entities import File, Dimension, Server, Gate, Route, FileServerAssociation
from dimensigon.use_cases.file_sync import FileSync
from dimensigon.utils.helpers import get_now
from dimensigon.web import create_app, db
from tests.base import AppScopedSession
from tests.helpers import generate_dimension_json_data, set_callbacks

now = get_now()


class TestFileSync(TestCase, AppScopedSession):

    @classmethod
    def setUpClass(cls) -> None:
        cls.dim = generate_dimension_json_data()

    def setUp(self) -> None:
        super().setUp()
        self.set_test_scoped_session(db)
        # create the app with common test config
        self.app1 = create_app('test')
        self.app1.config['SERVER_NAME'] = 'node1'

        # self.app1.config['SECURIZER'] = True
        self.client1 = self.app1.test_client()

        self.app2 = create_app('test')
        self.app2.config['SERVER_NAME'] = 'node2'
        # self.app2.config['SECURIZER'] = True
        self.client2 = self.app2.test_client()

        self.app3 = create_app('test')
        self.app3.config['SERVER_NAME'] = 'node3'
        # self.app3.config['SECURIZER'] = True
        self.client3 = self.app3.test_client()

        self.ctx = self.app1.app_context()
        self.ctx.push()

        self.fill_database('node1')

        with self.app2.app_context():
            self.fill_database('node2')

        with self.app3.app_context():
            self.fill_database('node3')

        self.source_path = '/node1'
        self.dest_path2 = '/node2'
        self.dest_path3 = '/node3'
        self.filename = 'sync_file'
        self.filename2 = 'sync_file2'
        self.content = b'content file to be sync'
        self.setUpPyfakefs()
        self.fs.create_dir(self.source_path)
        self.fs.create_dir(self.dest_path2)
        self.fs.create_dir(self.dest_path3)
        self.fs.create_file(os.path.join(self.source_path, self.filename), contents=self.content)
        self.fs.create_file(os.path.join(self.source_path, self.filename2), contents=self.content)

        # start file_sync after fakefs instantiated
        self.file_sync = FileSync(self.app1, executor=ThreadPoolExecutor(), sync_interval=0.01,
                                  file_watches_refresh_period=0.01)

    def fill_database(self, node):
        db.create_all()
        d = Dimension.from_json(self.dim)
        d.current = True
        s1 = Server(id='00000000-0000-0000-0000-000000000001', name='node1', created_on=now, me=node == 'node1')
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=s1, port=5000, dns=s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2', created_on=now, me=node == 'node2')
        g21 = Gate(id='00000000-0000-0000-0000-000000000021', server=s2, port=5000, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3', created_on=now, me=node == 'node3')
        g31 = Gate(id='00000000-0000-0000-0000-000000000031', server=s3, port=5000, dns=s3.name)

        if node == 'node1':
            self.s1 = s1
            self.s2 = s2
            self.s3 = s3
            Route(s2, g21)
            Route(s3, g31)
        elif node == 'node2':
            Route(s1, g11)
        elif node == 'node3':
            Route(s1, g11)

        db.session.add_all([d, s1, s2, s3])
        db.session.commit()

    def tearDown(self) -> None:
        self.file_sync.stop()

        db.session.remove()
        db.drop_all()
        self.ctx.pop()

        with self.app2.app_context():
            db.session.remove()
            db.drop_all()

    @mock.patch('dimensigon.use_cases.file_sync.Observer.unschedule')
    @mock.patch('dimensigon.use_cases.file_sync.Observer.schedule')
    @aioresponses()
    @responses.activate
    def test_sync(self, mock_schedule, mock_unschedule, m):
        set_callbacks([('node1', self.client1), ('node2', self.client2), ('node3', self.client3)], m)

        # files in database before start FileSync
        f = File(source_server=self.s1, target=os.path.join(self.source_path, self.filename),
                 destination_servers=[(self.s2, self.dest_path2)])
        db.session.add(f)
        db.session.commit()
        self.file_sync.start()
        start = time.time()
        while not os.path.exists(os.path.join(self.dest_path2, self.filename)):
            time.sleep(0.05)
            if time.time() - start > 5:
                break

        self.assertTrue(os.path.exists(os.path.join(self.dest_path2, self.filename)))

        self.assertEqual(self.content, open(os.path.join(self.dest_path2, self.filename), 'rb').read())

        # add file once FileSync started
        f = File(source_server=self.s1, target=os.path.join(self.source_path, self.filename2),
                 destination_servers=[(self.s2, self.dest_path2)])
        db.session.add(f)
        db.session.commit()
        start = time.time()
        while not os.path.exists(os.path.join(self.dest_path2, self.filename2)):
            time.sleep(0.05)
            if (time.time() - start) > 5:
                break

        self.assertTrue(os.path.exists(os.path.join(self.dest_path2, self.filename2)))

        self.assertEqual(self.content, open(os.path.join(self.dest_path2, self.filename2), 'rb').read())

        # add server into file once FileSync started
        fsa = FileServerAssociation(file=f, destination_server=self.s3, dest_folder=self.dest_path3)
        db.session.add(fsa)
        db.session.commit()

        print(f'adding file {fsa.file.target} for server {fsa.destination_server.name}')
        self.file_sync.add(fsa.file, fsa.destination_server)

        start = time.time()
        while not os.path.exists(os.path.join(self.dest_path3, self.filename2)):
            time.sleep(0.05)
            if (time.time() - start) > 5:
                break

        self.assertTrue(os.path.exists(os.path.join(self.dest_path3, self.filename2)))

        self.assertEqual(self.content, open(os.path.join(self.dest_path3, self.filename2), 'rb').read())

        # change content from file
        with open(f.target, 'wb') as fh:
            fh.write(b'new content to be synced')
        time.sleep(0.5)
        self.file_sync.add(fsa.file)

        start = time.time()
        while open(os.path.join(self.dest_path2, self.filename2), 'rb').read() != b'new content to be synced':
            time.sleep(0.05)
            if (time.time() - start) > 5:
                break

        self.assertEqual(b'new content to be synced',
                         open(os.path.join(self.dest_path2, self.filename2), 'rb').read())

        self.assertEqual(b'new content to be synced',
                         open(os.path.join(self.dest_path3, self.filename2), 'rb').read())
