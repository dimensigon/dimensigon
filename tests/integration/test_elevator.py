import logging
import os
import os.path
import tempfile
from subprocess import CompletedProcess
from unittest import TestCase
from unittest.mock import patch, mock_open

import dimensigon.defaults as d
from elevator import _upgrade, HOME, DM_ROOT, FAILED_VERSIONS


class TestElevator(TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.gettempdir()
        self.deployable = 'dimensigon.tar.gz'
        self.version = '1.0'
        self.old_home = os.path.join(DM_ROOT, 'dimensigon')
        self.new_home = os.path.join(DM_ROOT, 'dimensigon_' + self.version)

    @patch('elevator.run')
    @patch('elevator.os.rmdir')
    @patch('elevator.os.chdir')
    @patch('elevator.daemon_running')
    @patch('elevator.start_daemon')
    @patch('elevator.stop_daemon')
    @patch('elevator.shutil')
    @patch('elevator.os.path.exists')
    @patch('elevator.get_hc')
    def test_upgrade(self, mock_get_hc, mock_exists, mock_shutil, mock_stop, mock_start, mock_daemon, mock_chdir,
                     mock_rmdir, mock_run):
        mock_daemon.return_value = True
        mock_stop.return_value = True
        mock_start.return_value = True
        mock_get_hc.side_effect = [{"version": '0.0',
                                    "elevator_version": '0.0',
                                    "catalog_version": "20190401000000000000",
                                    "scheduler": "running",
                                    "neighbours": [],
                                    "services": []
                                    },
                                   {"version": self.version,
                                    "elevator_version": '0.9',
                                    "catalog_version": "20190401000000000000",
                                    "scheduler": "running",
                                    "neighbours": [],
                                    "services": []
                                    }
                                   ]

        mock_exists.return_value = False
        mock_run.return_value = CompletedProcess((), 0, 'stdout', '')

        import elevator
        elevator.host = '127.0.0.1:5000'
        # runner = CliRunner()
        # result = runner.invoke(upgrade, ['deployable.tar.gz', '1.0'], catch_exceptions=False)
        _upgrade(dict(deployable=self.deployable, version=self.version, dm_url=f"https://127.0.0.1:{d.LOOPBACK_PORT}"))

        # extract new version
        self.assertEqual(((self.new_home,),), mock_shutil.rmtree.call_args_list[0])
        mock_shutil.unpack_archive.assert_called_once_with(self.deployable, self.temp_dir)
        self.assertEqual(((os.path.join(self.temp_dir, 'dimensigon'), self.new_home),),
                         mock_shutil.copytree.call_args_list[0])

        # copy config files and DB from old version to new version
        self.assertGreaterEqual(mock_shutil.copy2.call_count, 1)
        self.assertGreaterEqual(mock_shutil.copytree.call_count, 1)

        # migration
        mock_run.assert_called_once()

        # stop old version
        mock_stop.assert_called_once()

        # change working dir to new home
        mock_chdir.assert_called_once_with(self.new_home)

        #####################
        # start NEW version #
        #####################
        mock_start.assert_called_once_with(self.new_home, elevator.logger.level != logging.DEBUG)
        mock_daemon.assert_called_once()

    @patch('elevator.run')
    @patch('elevator.os.rmdir')
    @patch('elevator.os.chdir')
    @patch('elevator.daemon_running')
    @patch('elevator.start_daemon')
    @patch('elevator.stop_daemon')
    @patch('elevator.shutil')
    @patch('elevator.os.path.exists')
    @patch('elevator.get_hc')
    def test_upgrade_error_new_version(self, mock_get_hc, mock_exists, mock_shutil, mock_stop, mock_start, mock_daemon,
                                       mock_chdir, mock_rmdir, mock_run):
        mock_daemon.side_effect = [False, True]
        mock_stop.return_value = True
        mock_start.return_value = True
        mock_get_hc.side_effect = [{"version": '0.0',
                                    "elevator_version": '0.0',
                                    "catalog_version": "20190401000000000000",
                                    "scheduler": "running",
                                    "neighbours": [],
                                    "services": []
                                    },
                                   {"version": '0.0',
                                    "elevator_version": '0.0',
                                    "catalog_version": "20190401000000000000",
                                    "scheduler": "running",
                                    "neighbours": [],
                                    "services": []
                                    }
                                   ]

        mock_exists.return_value = False
        mock_run.return_value = CompletedProcess((), 0, 'stdout', '')

        import elevator
        elevator.host = '127.0.0.1:5000'

        # runner = CliRunner()
        # result = runner.invoke(upgrade, ['deployable.tar.gz', '1.0'], catch_exceptions=False)
        m = mock_open()
        with patch('elevator.open', m):
            _upgrade(
                dict(deployable=self.deployable, version=self.version))

        # extract new version
        self.assertEqual(((self.new_home,),), mock_shutil.rmtree.call_args_list[0])
        mock_shutil.unpack_archive.assert_called_once_with(self.deployable, self.temp_dir)
        self.assertEqual(((os.path.join(self.temp_dir, 'dimensigon'), self.new_home),),
                         mock_shutil.copytree.call_args_list[0])

        # copy config files and DB from old version to new version
        self.assertGreaterEqual(mock_shutil.copy2.call_count, 1)
        self.assertGreaterEqual(mock_shutil.copytree.call_count, 1)

        # migration
        mock_run.assert_called_once()

        # stop old version
        # mock_stop.assert_called_once()

        # change working dir to new home
        # mock_chdir.assert_called_once_with(self.new_home)

        #####################
        # start NEW version #
        #####################
        # mock_start.assert_called_once_with(self.new_home, logging.root.level != logging.DEBUG)
        # mock_daemon.assert_called_once()

        # kill daemon if running
        self.assertEqual(2, mock_stop.call_count)

        self.assertListEqual([((self.new_home,),), ((HOME,),)], mock_chdir.call_args_list)

        m.assert_called_once_with(FAILED_VERSIONS, 'a')
        handle = m()
        handle.write.assert_called_once_with(self.version + '\n')

        # start old version
        self.assertListEqual(
            [((self.new_home, elevator.logger.level != logging.DEBUG),),
             ((self.old_home, elevator.logger.level != logging.DEBUG),)],
            mock_start.call_args_list)

        self.assertEqual(2, mock_daemon.call_count)
