import base64
from unittest import TestCase, mock
from unittest.mock import patch

from aioresponses import aioresponses, CallbackResult
from asynctest.mock import patch as async_patch

from dm.domain.entities import Server, Route, Log
from dm.use_cases.log_sender import LogSender
from dm.use_cases.log_sender import _PygtailBuffer, Pygtail
from dm.utils.asyncio import run
from dm.web import create_app, db


class TestServer(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.source = Server('source', port=8000, me=True)
        self.dest = Server('dest', port=8000)
        Route(self.dest, cost=0)
        db.session.add_all([self.source, self.dest])
        _PygtailBuffer._fh = mock.MagicMock()
        self.log_sender = LogSender()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dm.use_cases.log_sender.os.walk', autospec=True)
    @patch('dm.use_cases.log_sender.os.path.isfile', autospec=True)
    @patch.object(Pygtail, 'update_offset_file')
    @patch.object(_PygtailBuffer, 'readlines', return_value='content', autospec=True)
    @aioresponses()
    def test_log_sender_file(self, mock_pb_rl, mock_pt_uof, mock_isfile, mock_walk, m):
        def callback(url, **kwargs):
            self.assertDictEqual(
                {"file": '/dm/logs/dm.log', 'data': base64.b64encode('content'.encode()).decode('ascii')},
                kwargs['json'])
            return CallbackResult('POST', status=200)

        m.post(self.dest.url('api_1_0.logresource', log_id='aaaaaaaa-1234-5678-1234-56781234aaa1'), callback=callback)

        mock_isfile.return_value = True

        log = Log(id='aaaaaaaa-1234-5678-1234-56781234aaa1', source_server=self.source, target='/var/log/dm.log',
                  destination_server=self.dest, dest_folder='/dm/logs/')
        db.session.add(log)

        run(self.log_sender.send_new_data())

        mock_isfile.assert_called_once()
        mock_walk.assert_not_called()
        mock_pb_rl.assert_called_once()
        mock_pt_uof.assert_called_once()

    @patch('dm.use_cases.log_sender.os.path.isfile', autospec=True)
    @patch.object(Pygtail, 'update_offset_file')
    @patch.object(_PygtailBuffer, 'readlines', return_value='content', autospec=True)
    @aioresponses()
    def test_log_sender_file_no_dest_folder(self, mock_pb_rl, mock_pt_uof, mock_isfile, m):
        def callback(url, **kwargs):
            self.assertDictEqual(
                {"file": '/var/log/dm.log', 'data': base64.b64encode('content'.encode()).decode('ascii')},
                kwargs['json'])
            return CallbackResult('POST', status=200)

        m.post(self.dest.url('api_1_0.logresource', log_id='aaaaaaaa-1234-5678-1234-56781234aaa1'), callback=callback)

        mock_isfile.return_value = True

        log = Log(id='aaaaaaaa-1234-5678-1234-56781234aaa1', source_server=self.source, target='/var/log/dm.log',
                  destination_server=self.dest, dest_folder=None)
        db.session.add(log)

        run(self.log_sender.send_new_data())

        mock_isfile.assert_called_once()
        mock_pb_rl.assert_called_once()
        mock_pt_uof.assert_called_once()

    @async_patch('dm.use_cases.log_sender.async_post', autospec=True)
    @patch('dm.use_cases.log_sender.os.walk', autospec=True)
    @patch('dm.use_cases.log_sender.os.path.isfile', autospec=True)
    @patch.object(Pygtail, 'update_offset_file')
    @patch.object(_PygtailBuffer, 'readlines', side_effect=['content1', 'newcontent2'], autospec=True)
    @aioresponses()
    def test_log_sender_folder(self, mock_pb_rl, mock_pt_uof, mock_isfile, mock_walk, mock_post, m):

        def callback(url, **kwargs):
            if kwargs['json']['file'] == '/dm/logs/log1':
                self.assertDictEqual(
                    {"file": '/dm/logs/log1', 'data': base64.b64encode('content1'.encode()).decode('ascii')},
                    kwargs['json'])
                return CallbackResult('POST', payload={'offset': 8}, status=200)
            elif kwargs['json']['file'] == '/dm/logs/dir1/log2':
                self.assertDictEqual(
                    {"file": '/dm/logs/dir1/log2', 'data': base64.b64encode('newcontent2'.encode()).decode('ascii')},
                    kwargs['json'])
                return CallbackResult('POST', payload={'offset': 11}, status=200)
            else:
                raise

        mock_post.side_effect = [({'offset': 8}, 200), ({'offset': 11}, 200), ({'offset': 8}, 200)]

        m.post(self.dest.url('api_1_0.logresource', log_id='aaaaaaaa-1234-5678-1234-56781234aaa1'), callback=callback)
        m.post(self.dest.url('api_1_0.logresource', log_id='aaaaaaaa-1234-5678-1234-56781234aaa1'), callback=callback)
        m.post(self.dest.url('api_1_0.logresource', log_id='aaaaaaaa-1234-5678-1234-56781234aaa1'), callback=callback)

        mock_isfile.return_value = False
        mock_walk.side_effect = [
            [('/var/log', ['dir1'], ['log1', 'file']), ('/var/log/dir1', ['dir2'], ['log2'])],
            [('/var/log', ['dir1'], ['log1', 'file']), ('/var/log/dir1', ['dir2'], [])]
        ]

        log = Log(id='aaaaaaaa-1234-5678-1234-56781234aaa1', source_server=self.source, target='/var/log',
                  destination_server=self.dest, dest_folder='/dm/logs/', include='^(log|dir)', exclude='^dir2',
                  recursive=True)
        db.session.add(log)

        run(self.log_sender.send_new_data())

        mock_isfile.assert_called_once()
        self.assertEqual(2, mock_pb_rl.call_count)
        self.assertEqual(2, mock_pt_uof.call_count)
