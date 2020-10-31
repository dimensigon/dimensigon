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
from dimensigon.web import db
from tests import base
from tests.helpers import set_callbacks

now = get_now()


class TestFileSync(base.ThreeNodeMixin, TestCase):

    def setUp(self) -> None:
        super().setUp()

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
        self.file_sync = FileSync(self.app, executor=ThreadPoolExecutor(), sync_interval=0.01,
                                  file_watches_refresh_period=0.01)

    def tearDown(self) -> None:
        self.file_sync.stop()
        super().tearDown()

    @mock.patch('dimensigon.use_cases.file_sync.Observer.unschedule')
    @mock.patch('dimensigon.use_cases.file_sync.Observer.schedule')
    @aioresponses()
    @responses.activate
    def test_sync(self, mock_schedule, mock_unschedule, m):
        set_callbacks([('node1', self.client), ('node2', self.client2), ('node3', self.client3)], m)

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
        self.file_sync.add(fsa.file.id, fsa.destination_server)

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
        while open(os.path.join(self.dest_path3, self.filename2), 'rb').read() != b'new content to be synced':
            time.sleep(0.05)
            if (time.time() - start) > 5:
                break

        self.assertEqual(b'new content to be synced',
                         open(os.path.join(self.dest_path2, self.filename2), 'rb').read())

        self.assertEqual(b'new content to be synced',
                         open(os.path.join(self.dest_path3, self.filename2), 'rb').read())

    @mock.patch('dimensigon.use_cases.file_sync.Observer.unschedule')
    @mock.patch('dimensigon.use_cases.file_sync.Observer.schedule')
    @aioresponses()
    @responses.activate
    def test_sync_file_not_exists(self, mock_schedule, mock_unschedule, m):
        set_callbacks([('node1', self.client), ('node2', self.client2), ('node3', self.client3)], m)

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