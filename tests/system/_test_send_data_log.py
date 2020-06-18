import os
import time

from asynctest import patch, TestCase
from testfixtures import LogCapture

from dm.domain.entities.log import Log
from dm.utils.helpers import encode
from dm.web import create_app, repo, interactor
from tests.helpers import set_response_from_mock, wait_mock_called
from tests.system.data import Server1, Server2

DEST_FOLDER = os.path.dirname(os.path.abspath(__file__))


class TestSendDataLog(TestCase):

    def setUp(self) -> None:
        self.file1 = os.path.join(DEST_FOLDER, 'server1.tempfile.log')
        self.file2 = os.path.join(DEST_FOLDER, 'server2.tempfile.log')
        self.remove_files()

        self.app1 = create_app(Server1())
        self.app2 = create_app(Server2())

        self.client1 = self.app1.test_client()
        self.client2 = self.app2.test_client()
        self.lines = ['line 1\nline 2\n', 'line 3\n', 'line 4\nline 5\n']
        self.i = 0
        self.append_data()

    def append_data(self):
        with open(self.file1, 'a') as temp:
            temp.write(self.lines[self.i])
        self.i += 1

    def get_file_offset(self):
        try:
            with open(self.file1 + '.offset', 'r') as temp:
                return int(temp.readlines()[1].strip())
        except:
            return None

    def get_current_offset(self):
        with open(self.file1, 'r') as fd:
            fd.seek(0, 2)
            return fd.tell()

    def remove_files(self):
        for file in (self.file1, self.file2):
            try:
                os.remove(file)
            except:
                pass
            try:
                os.remove(file + '.offset')
            except:
                pass

    def tearDown(self, c=0) -> None:
        with self.app1.app_context():
            interactor.stop_send_data_logs()
        self.remove_files()

    @patch('dm.network.gateway.requests.post')
    def test_send_data_log(self, mock_post):
        set_response_from_mock(mock_post, url='http://server2.localdomain:81/socket?', status=200, json='')
        with self.app1.app_context():
            log = Log(file=self.file1, server=repo.ServerRepo.find('bbbbbbbb-1234-5678-1234-56781234bbb2'),
                      dest_folder=DEST_FOLDER, dest_name=os.path.basename(self.file2))
            repo.LogRepo.add(log)
            del log

            interactor._delay = None
            resp = interactor.send_data_logs(blocking=False, delay=None)
            wait_mock_called(mock_post, 1, 10)

            mock_post.assert_called_once_with('http://server2.localdomain:81/socket',
                                              json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2',
                                                    'data': encode(filename=os.path.basename(self.file2),
                                                                   data_log=self.lines[0], dest_folder=DEST_FOLDER)})

        with self.app2.app_context():
            self.client2.post('/socket', json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2',
                                               'data': encode(filename=os.path.basename(self.file2),
                                                              data_log=self.lines[0], dest_folder=DEST_FOLDER)})
            c = 0
            while not os.path.exists(self.file2) and c < 50:
                time.sleep(0.01)
                c += 1
            self.assertTrue(os.path.exists(self.file2))
            with open(self.file2) as fd:
                self.assertEqual(self.lines[0], fd.read())

        with self.app1.app_context():
            self.append_data()
            # force to awake thread
            interactor._awake.set()
            # wait until it reads the new data
            wait_mock_called(mock_post, 2, 10)
            interactor._awake.clear()
            mock_post.assert_called_with('http://server2.localdomain:81/socket',
                                         json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2',
                                               'data': encode(filename=os.path.basename(self.file2),
                                                              data_log=self.lines[1], dest_folder=DEST_FOLDER)})

        with self.app2.app_context():
            self.client2.post('/socket', json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2',
                                               'data': encode(filename=os.path.basename(self.file2),
                                                              data_log=self.lines[1], dest_folder=DEST_FOLDER)})
            c = 0
            while not os.path.exists(self.file2) and c < 50:
                time.sleep(0.01)
                c += 1
            self.assertTrue(os.path.exists(self.file2))
            with open(self.file2) as fd:
                self.assertEqual(''.join(self.lines[0:2]), fd.read())

    @patch('dm.network.gateway.requests.post')
    def test_send_data_log_with_error(self, mock_post):

        with self.app1.app_context():
            log = Log(file=self.file1, server=repo.ServerRepo.find('bbbbbbbb-1234-5678-1234-56781234bbb2'),
                      dest_folder=DEST_FOLDER, dest_name=os.path.basename(self.file2))
            repo.LogRepo.add(log)
            del log

            set_response_from_mock(mock_post, url='http://server2.localdomain:81/socket?', status=500,
                                   json='{"error": "Permission Denied"}')
            interactor._delay = None

            with LogCapture() as l:
                resp = interactor.send_data_logs(blocking=False, delay=None)
                wait_mock_called(mock_post, 1, 50)
                self.assertTrue(True)

            self.assertFalse(os.path.exists(self.file1 + '.offset'))

            mock_post.assert_called_once_with('http://server2.localdomain:81/socket',
                                              json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2',
                                                    'data': encode(filename=os.path.basename(self.file2),
                                                                   data_log=self.lines[0], dest_folder=DEST_FOLDER)})

            set_response_from_mock(mock_post, url='http://server2.localdomain:81/socket?', status=200, json='')

            self.append_data()
            # force to awake thread
            interactor._awake.set()
            # wait until it reads the new data
            wait_mock_called(mock_post, 2, 50)
            interactor._awake.clear()
            mock_post.assert_called_with('http://server2.localdomain:81/socket',
                                         json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2',
                                               'data': encode(filename=os.path.basename(self.file2),
                                                              data_log=''.join(self.lines[0:2]),
                                                              dest_folder=DEST_FOLDER)})
