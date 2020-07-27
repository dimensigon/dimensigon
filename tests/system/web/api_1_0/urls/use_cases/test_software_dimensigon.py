import base64
from unittest import TestCase
from unittest.mock import patch, mock_open

from flask import url_for
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import create_app, db


class Test(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
        db.create_all()
        set_initial()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dimensigon.web.api_1_0.urls.use_cases.open', mock_open(read_data=b'bibble'))
    @patch('dimensigon.web.api_1_0.urls.use_cases.os.listdir')
    def test_software_dimensigon(self, mock_os):
        with patch('dimensigon.web.api_1_0.urls.use_cases.dimensigon.__version__', '1.2.0'):
            mock_os.return_value = ['file1', 'dimensigon-v1.0.0.tar.gz', 'dimensigon-v1.2.0.tar.gz',
                                    'dimensigon-v1.1.0.tar.gz']
            resp = self.client.get(url_for('api_1_0.software_dimensigon'), headers=self.auth.header)

            self.assertEqual(200, resp.status_code)

            self.assertDictEqual({'filename': 'dimensigon-v1.2.0.tar.gz', 'version': 'v1.2.0',
                                  'content': base64.b64encode(b'bibble').decode('ascii')}, resp.get_json())

            # version on filesystem bigger than actual
            mock_os.return_value = ['file1', 'dimensigon-1.2.0.tar.gz', 'dimensigon-1.3.0.tar.gz',
                                    'dimensigon-1.0.0.tar.gz']
            resp = self.client.get(url_for('api_1_0.software_dimensigon'), headers=self.auth.header)

            self.assertEqual(200, resp.status_code)

            self.assertDictEqual({'filename': 'dimensigon-1.3.0.tar.gz', 'version': '1.3.0',
                                  'content': base64.b64encode(b'bibble').decode('ascii')}, resp.get_json())

            # version on filesystem lower than actual
            mock_os.return_value = ['file1', 'dimensigon-v1.0.0.tar.gz', 'dimensigon-v0.9.0.tar.gz']
            resp = self.client.get(url_for('api_1_0.software_dimensigon'), headers=self.auth.header)

            self.assertEqual(204, resp.status_code)
