from unittest import TestCase
from unittest.mock import patch

from flask_jwt_extended import create_access_token
from pkg_resources import parse_version

from dm.web import create_app, db
from dm.web.background_tasks import upgrade_version, catalog_logger
from dm.web.network import HTTPBearerAuth


class Test(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('test'))
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dm.web.background_tasks.get_auth_root')
    @patch('dm.web.background_tasks.run_elevator')
    @patch('dm.web.background_tasks.get_software')
    @patch('dm.web.background_tasks.dm_version', '1.0')
    def test_upgrade_version(self, mock_get_software, mock_run_elevator, mock_auth):
        ret = upgrade_version({1: (dict(version='0.9'), 200),
                               2: (dict(version='1.0'), 200)})
        self.assertFalse(ret)

        mock_auth.return_value = 'root'
        mock_get_software.return_value = (None, None)
        ret = upgrade_version({1: (dict(version='1.1'), 200),
                               2: (dict(version='1.0'), 200)})
        self.assertFalse(ret)
        mock_get_software.assert_called_once_with(1, 'root')
        mock_run_elevator.assert_not_called()

        mock_get_software.return_value = ('file', '1.1')
        ret = upgrade_version({1: (dict(version='1.1'), 200),
                               2: (dict(version='1.0'), 200)})
        self.assertTrue(ret)
        mock_run_elevator.assert_called_once_with('file', parse_version('1.1'), catalog_logger)
