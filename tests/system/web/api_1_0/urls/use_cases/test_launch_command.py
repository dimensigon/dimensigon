from unittest import TestCase, mock

from flask import url_for

from dimensigon.web.api_1_0.urls.use_cases import wrap_sudo
from tests.base import TwoNodeMixin, VirtualNetworkMixin


class TestLaunchCommand(VirtualNetworkMixin, TwoNodeMixin, TestCase):

    @mock.patch('dimensigon.web.api_1_0.urls.use_cases.subprocess.Popen')
    def test_launch_command(self, mock_popen):
        popen_mock = mock.MagicMock()
        mock_popen.return_value = popen_mock
        popen_mock.communicate.return_value = ('output', '')
        type(popen_mock).returncode = mock.PropertyMock(return_value=0)

        resp = self.client.post(url_for('api_1_0.launch_command'),
                                json={"command": "ls -l", "target": 'all', 'timeout': 1},
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual({self.s1.id: {'stdout': ['output'], 'stderr': [''], 'returncode': 0},
                              self.s2.id: {'stdout': ['output'], 'stderr': [''], 'returncode': 0},
                              'cmd': wrap_sudo('root', 'ls -l'),
                              'input': None},
                             resp.get_json())

        self.assertEqual(2, mock_popen.call_count)

        self.assertTupleEqual((wrap_sudo('root', 'ls -l'),), mock_popen.call_args[0])

        resp = self.client.post(url_for('api_1_0.launch_command'),
                                json={"command": "ls -l", "target": [self.s2.id], 'timeout': 1},
                                headers=self.auth.header)
        self.assertEqual(200, resp.status_code)
        self.assertDictEqual({self.s2.id: {'stdout': ['output'], 'stderr': [''], 'returncode': 0},
                              'cmd': wrap_sudo('root', 'ls -l'),
                              'input': None},
                             resp.get_json())

        resp = self.client.post(url_for('api_1_0.launch_command'),
                                json={"command": "ls -l", "target": self.s1.id, 'timeout': 1},
                                headers=self.auth.header)
        self.assertEqual(200, resp.status_code)
        self.assertDictEqual({self.s1.id: {'stdout': ['output'], 'stderr': [''], 'returncode': 0},
                              'cmd': wrap_sudo('root', 'ls -l'),
                              'input': None},
                             resp.get_json())

    @mock.patch('dimensigon.web.api_1_0.urls.use_cases.subprocess.Popen')
    def test_launch_command_timeout(self, mock_popen):
        args = wrap_sudo('root', ['sleep', '10'])
        cmd = 'sleep 10'
        popen_mock = mock.MagicMock()
        mock_popen.return_value = popen_mock
        popen_mock.communicate.side_effect = [TimeoutError, ('', '')]
        type(popen_mock).returncode = mock.PropertyMock(return_value=0)

        resp = self.client.post(url_for('api_1_0.launch_command'),
                                json={"command": cmd, "target": 'node1', 'timeout': 1},
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        data.pop('cmd')
        data.pop('input')
        self.assertDictEqual(
            {self.s1.id: {'error': f"Command '{wrap_sudo('root', cmd)}' timed out after 1 seconds",
                          'stdout': [''], 'stderr': ['']},

             },
            data)

    def test_launch_command_rm_recursive(self):
        resp = self.client.post(url_for('api_1_0.launch_command'),
                                json={"command": "rm -fr /folder", "target": "all", 'timeout': 1},
                                headers=self.auth.header)

        self.assertEqual(403, resp.status_code)
        self.assertDictEqual({'error': 'rm with recursion is not allowed'},
                             resp.get_json())
