import os
import queue
import threading
from unittest import mock

from pyfakefs.fake_filesystem_unittest import TestCase

from dimensigon.domain.entities import File, FileServerAssociation
from dimensigon.use_cases.file_sync import FileSync
from dimensigon.utils.helpers import get_now
from dimensigon.web import db
from tests import base

now = get_now()


class MPQueue(queue.Queue):

    def safe_get(self, timeout=0):
        try:
            if timeout is None:
                return self.get(block=False)
            else:
                return self.get(block=True, timeout=timeout)
        except queue.Empty:
            return None

    def safe_put(self, item, timeout=0):
        try:
            self.put(item, block=True, timeout=timeout)
            return True
        except queue.Full:
            return False

    def drain(self):
        item = self.safe_get()
        while item:
            yield item
            item = self.safe_get()

    def safe_close(self):
        num_left = sum(1 for __ in self.drain())
        return num_left


class TestFileSync(base.VirtualNetworkMixin, base.ThreeNodeMixin,  TestCase):

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

        self.mock_queue = mock.Mock()
        self.mock_dm = mock.Mock()
        self.mock_dm.flask_app = self.app
        self.mock_dm.engine = db.engine
        self.mock_dm.cluster_manager.get_alive.return_value = [self.s1.id, self.s2.id, self.s3.id]
        self.mock_dm.server_id = self.s1.id

        # start file_sync after fakefs instantiated
        # mock MPQueue cause Multiprocessing Queue uses FileSystem and we are mocking it with fakefs
        with mock.patch('dimensigon.use_cases.file_sync.MPQueue', MPQueue):
            self.file_sync = FileSync("FileSync", startup_event=threading.Event(), shutdown_event=threading.Event(),
                                      publish_q=self.mock_queue, event_q=None, dimensigon=self.mock_dm,
                                      file_sync_period=0,
                                      file_watches_refresh_period=0,
                                      max_allowed_errors=1,
                                      retry_blacklist=1)

    def tearDown(self) -> None:
        try:
            self.file_sync.shutdown()
        except:
            pass
        super().tearDown()

    @mock.patch('dimensigon.use_cases.file_sync.Observer.unschedule')
    @mock.patch('dimensigon.use_cases.file_sync.Observer.schedule')
    def test_sync(self, mock_schedule, mock_unschedule):

        # files in database before start FileSync
        f = File(source_server=self.s1, target=os.path.join(self.source_path, self.filename),
                 destination_servers=[(self.s2, self.dest_path2)])
        db.session.add(f)
        db.session.commit()

        self.file_sync.startup()
        self.file_sync.main_func()

        self.assertTrue(os.path.exists(os.path.join(self.dest_path2, self.filename)))

        self.assertEqual(self.content, open(os.path.join(self.dest_path2, self.filename), 'rb').read())

        # add file once FileSync started
        f = File(source_server=self.s1, target=os.path.join(self.source_path, self.filename2),
                 destination_servers=[(self.s2, self.dest_path2)])
        db.session.add(f)
        db.session.commit()
        self.file_sync.main_func()
        self.assertTrue(os.path.exists(os.path.join(self.dest_path2, self.filename2)))

        self.assertEqual(self.content, open(os.path.join(self.dest_path2, self.filename2), 'rb').read())

        # add server into file once FileSync started
        fsa = FileServerAssociation(file=f, destination_server=self.s3, dest_folder=self.dest_path3)
        db.session.add(fsa)
        db.session.commit()

        print(f'adding file {fsa.file.target} for server {fsa.destination_server.name}')
        self.file_sync.add(fsa.file.id, fsa.destination_server)

        self.file_sync.main_func()

        self.assertTrue(os.path.exists(os.path.join(self.dest_path3, self.filename2)))

        self.assertEqual(self.content, open(os.path.join(self.dest_path3, self.filename2), 'rb').read())

        # change content from file
        with open(f.target, 'wb') as fh:
            fh.write(b'new content to be synced')
        self.file_sync.add(fsa.file)

        self.file_sync.main_func()

        self.assertEqual(b'new content to be synced',
                         open(os.path.join(self.dest_path2, self.filename2), 'rb').read())

        self.assertEqual(b'new content to be synced',
                         open(os.path.join(self.dest_path3, self.filename2), 'rb').read())

    @mock.patch('dimensigon.use_cases.file_sync.Observer.unschedule')
    @mock.patch('dimensigon.use_cases.file_sync.Observer.schedule')
    def test_sync_file_not_exists(self, mock_schedule, mock_unschedule):
        # files in database before start FileSync
        f = File(source_server=self.s1, target=os.path.join(self.source_path, self.filename + 'x'),
                 destination_servers=[(self.s2, self.dest_path2)])
        db.session.add(f)
        db.session.commit()

        self.file_sync.startup()
        self.file_sync.main_func()

        self.assertFalse(os.path.exists(os.path.join(self.dest_path2, self.filename) + 'x'))
