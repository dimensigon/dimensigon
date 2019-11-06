from unittest import TestCase, mock

from dm.use_cases import deployment
from dm.utils.typos import Params


class TestNativeCommand(TestCase):
    def test_execute(self):
        nc = deployment.NativeOperation('mkdir {dir}', expected_output=None, expected_rc=None, system_kwargs=None)
        with mock.patch('subprocess.run', return_value=(0, 'stdout', 'stderr')) as mocked_run:
            rc = nc.execute(Params({'dir': 'c:\\test'}))
            mocked_run.assert_called_once_with(['mkdir', 'c:\\test'], capture_output=True, shell=True, timeout=300)
            self.assertTrue(rc.success)

        nc = deployment.NativeOperation('mkdir {dir}', expected_output=None, expected_rc=None,
                                        system_kwargs={'timeout': 50})
        with mock.patch('subprocess.run', return_value=(0, 'stdout', 'stderr')) as mocked_run:
            rc = nc.execute(Params({'dir': 'c:\\test'}))
            mocked_run.assert_called_once_with(['mkdir', 'c:\\test'], capture_output=True, shell=True, timeout=50)
            self.assertTrue(rc.success)

        nc = deployment.NativeOperation('mkdir {dir}', expected_output='stdout', expected_rc=None, system_kwargs=None)
        with mock.patch('subprocess.run', return_value=(0, '', 'stderr')):
            rc = nc.execute(Params({'dir': 'c:\\test'}))
            self.assertFalse(rc.success)

        nc = deployment.NativeOperation('mkdir {dir}', expected_output='stdout', expected_rc=0, system_kwargs=None)
        with mock.patch('subprocess.run', return_value=(1, 'stdout', 'stderr')):
            rc = nc.execute(Params({'dir': 'c:\\test'}))
            self.assertFalse(rc.success)

        nc = deployment.NativeOperation('mkdir {dir}', expected_output='stdout', expected_rc=1, system_kwargs=None)
        with mock.patch('subprocess.run', return_value=(1, 'stdout', 'stderr')):
            rc = nc.execute(Params({'dir': 'c:\\test'}))
            self.assertTrue(rc.success)
