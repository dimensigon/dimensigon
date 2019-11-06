import io
import sys
from unittest import TestCase
from unittest import mock

import asynctest as at
from asynctest import call

import dm.use_cases.exceptions as ue
import dm.use_cases.log_sender as ls

PY2 = sys.version_info[0] == 2


class TestLogSender(TestCase):

    def setUp(self) -> None:
        mocked_server = mock.MagicMock()
        self.mocked_log_repo = mock.MagicMock()
        self.mocked_log1, self.mocked_log2 = mock.MagicMock(), mock.MagicMock()
        self.mocked_log_repo.all.return_value = [self.mocked_log1, self.mocked_log2]
        mocked_container = mock.MagicMock()
        mocked_container.find_by_interface.return_value = self.mocked_log_repo
        self.mocked_mediator = mock.MagicMock()
        self.log_sender = ls.LogSender(mocked_container, self.mocked_mediator)

    def test_logs(self):
        self.assertListEqual([self.mocked_log1, self.mocked_log2], self.log_sender.logs)
        self.assertEqual(2, len(self.log_sender.buffer_data))

    def test_send_new_data(self):
        ls.MAX_LINES = 3
        self.mocked_log1.readlines.side_effect = [['1\n', '2\n', '3\n'], ['4\n', '5\n'], []]
        self.mocked_log2.readlines.side_effect = [[], ['a\n', 'b\n']]
        self.mocked_log1.binary = False
        self.mocked_log2.binary = False
        self.mocked_log1.file = "file1.log"
        self.mocked_log2.file = "file2.log"
        self.mocked_log1.dest_folder = 'dest_folder1'
        self.mocked_log2.dest_folder = 'dest_folder2'
        self.mocked_log1.server = 'server1'
        self.mocked_log2.server = 'server2'

        self.mocked_mediator.send_data_log = at.CoroutineMock(side_effect=['', '', '', '', '', ''])
        self.log_sender.send_new_data()
        self.assertEqual(2, self.mocked_mediator.send_data_log.await_count)
        self.assertListEqual([call('file1.log', 'server1', '1\n2\n3\n', 'dest_folder1'),
                              call('file1.log', 'server1', '4\n5\n', 'dest_folder1')],
                             self.mocked_mediator.send_data_log.await_args_list)

        self.log_sender.send_new_data()
        self.assertEqual(call('file2.log', 'server2', 'a\nb\n', 'dest_folder2'),
                         self.mocked_mediator.send_data_log.await_args)
        self.assertEqual(3, self.mocked_mediator.send_data_log.await_count)

    def test_send_new_data_with_error(self):
        ls.MAX_LINES = 3
        self.mocked_log1.readlines.side_effect = [['1\n', '2\n', '3\n'], ['4\n', '5\n'], []]
        self.mocked_log2.readlines.side_effect = [[], ['a\n', 'b\n']]
        self.mocked_log1.binary = False
        self.mocked_log2.binary = False
        self.mocked_log1.file = "file1.log"
        self.mocked_log2.file = "file2.log"
        self.mocked_log1.dest_folder = 'dest_folder1'
        self.mocked_log2.dest_folder = 'dest_folder2'
        self.mocked_log1.server = 'server1'
        self.mocked_log2.server = 'server2'

        old_stderr = sys.stderr
        sys.stderr = io.BytesIO() if PY2 else io.StringIO()

        self.mocked_mediator.send_data_log = at.CoroutineMock(
            side_effect=[ue.CommunicationError('server1', 'Error', 404), '', '', '', '', ''])
        self.log_sender.send_new_data()
        self.assertEqual(1, self.mocked_mediator.send_data_log.await_count)
        self.assertEqual(call('file1.log', 'server1', '1\n2\n3\n', 'dest_folder1'),
                         self.mocked_mediator.send_data_log.await_args)

        captured_value = sys.stderr.getvalue()
        sys.stderr = old_stderr

        self.assertEqual("Unable to send log information to 'server1' from file 'file1.log'. "
                         "HTTP code: 404. Response:\nError\n", captured_value)

        self.log_sender.send_new_data()
        self.assertListEqual([call('file1.log', 'server1', '1\n2\n3\n', 'dest_folder1'),
                              call('file1.log', 'server1', '1\n2\n3\n', 'dest_folder1'),
                              call('file2.log', 'server2', 'a\nb\n', 'dest_folder2'),
                              call('file1.log', 'server1', '4\n5\n', 'dest_folder1')],
                             self.mocked_mediator.send_data_log.await_args_list)
