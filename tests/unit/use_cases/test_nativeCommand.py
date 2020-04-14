from unittest import TestCase, mock

import dm.use_cases.operations


class TestNativeCommand(TestCase):
    def test_execute(self):
        nc = dm.use_cases.operations.NativeOperation('mkdir {dir}', expected_output=None, expected_rc=None,
                                                     system_kwargs=None)
        with mock.patch('subprocess.run', return_value=(0, 'stdout', 'stderr')) as mocked_run:
            rc = nc.execute(dict({'dir': 'c:\\test'}))
            mocked_run.assert_called_once_with(['mkdir', 'c:\\test'], capture_output=True, shell=True, timeout=300)
            self.assertTrue(rc.success)

        nc = dm.use_cases.operations.NativeOperation('mkdir {dir}', expected_output=None, expected_rc=None,
                                                     system_kwargs={'timeout': 50})
        with mock.patch('subprocess.run', return_value=(0, 'stdout', 'stderr')) as mocked_run:
            rc = nc.execute(dict({'dir': 'c:\\test'}))
            mocked_run.assert_called_once_with(['mkdir', 'c:\\test'], capture_output=True, shell=True, timeout=50)
            self.assertTrue(rc.success)

        nc = dm.use_cases.operations.NativeOperation('mkdir {dir}', expected_output='stdout', expected_rc=None,
                                                     system_kwargs=None)
        with mock.patch('subprocess.run', return_value=(0, '', 'stderr')):
            rc = nc.execute(dict({'dir': 'c:\\test'}))
            self.assertFalse(rc.success)

        nc = dm.use_cases.operations.NativeOperation('mkdir {dir}', expected_output='stdout', expected_rc=0,
                                                     system_kwargs=None)
        with mock.patch('subprocess.run', return_value=(1, 'stdout', 'stderr')):
            rc = nc.execute(dict({'dir': 'c:\\test'}))
            self.assertFalse(rc.success)

        nc = dm.use_cases.operations.NativeOperation('mkdir {dir}', expected_output='stdout', expected_rc=1,
                                                     system_kwargs=None)
        with mock.patch('subprocess.run', return_value=(1, 'stdout', 'stderr')):
            rc = nc.execute(dict({'dir': 'c:\\test'}))
            self.assertTrue(rc.success)
