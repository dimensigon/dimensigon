from subprocess import PIPE, CompletedProcess
from unittest import TestCase, mock

import dimensigon.use_cases.operations


class TestNativeCommand(TestCase):
    def test_execute(self):
        nc = dimensigon.use_cases.operations.ShellOperation('mkdir {{dir}}', expected_stdout=None, expected_rc=None,
                                                            system_kwargs=None)
        with mock.patch('dimensigon.utils.subprocess.run', return_value=CompletedProcess(args=(), returncode=0, stdout='stdout',
                                                                        stderr='stderr')) as mocked_run:
            rc = nc.execute(dict({'dir': 'c:\\test'}))
            mocked_run.assert_called_once_with('mkdir c:\\test', stdout=PIPE, stderr=PIPE, shell=True, timeout=300)
            self.assertTrue(rc.success)

        nc = dimensigon.use_cases.operations.ShellOperation('mkdir {{dir}}', expected_stdout=None, expected_rc=None,
                                                            system_kwargs={'timeout': 50})
        with mock.patch('dimensigon.utils.subprocess.run', return_value=CompletedProcess(args=(), returncode=0, stdout='stdout',
                                                                        stderr='stderr')) as mocked_run:
            rc = nc.execute(dict({'dir': 'c:\\test'}))
            mocked_run.assert_called_once_with('mkdir c:\\test', stdout=PIPE, stderr=PIPE, shell=True, timeout=50)
            self.assertTrue(rc.success)

        nc = dimensigon.use_cases.operations.ShellOperation('mkdir {{dir}}', expected_stdout='stdout', expected_rc=None,
                                                            system_kwargs=None)
        with mock.patch('dimensigon.utils.subprocess.run', return_value=CompletedProcess(args=(), returncode=0, stdout='',
                                                                        stderr='stderr')):
            rc = nc.execute(dict({'dir': 'c:\\test'}))
            self.assertFalse(rc.success)

        nc = dimensigon.use_cases.operations.ShellOperation('mkdir {dir}', expected_stdout='stdout', expected_rc=0,
                                                            system_kwargs=None)
        with mock.patch('dimensigon.utils.subprocess.run', return_value=CompletedProcess(args=(), returncode=1, stdout='stdout',
                                                                        stderr='stderr')):
            rc = nc.execute(dict({'dir': 'c:\\test'}))
            self.assertFalse(rc.success)

        nc = dimensigon.use_cases.operations.ShellOperation('mkdir {{dir}}', expected_stdout='stdout', expected_rc=1,
                                                            system_kwargs=None)
        with mock.patch('dimensigon.utils.subprocess.run', return_value=CompletedProcess(args=(), returncode=1, stdout='stdout',
                                                                        stderr='stderr')):
            rc = nc.execute(dict({'dir': 'c:\\test'}))
            self.assertTrue(rc.success)
