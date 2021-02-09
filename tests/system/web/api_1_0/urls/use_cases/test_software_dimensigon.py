import base64
from unittest.mock import patch, mock_open, PropertyMock

from flask import url_for

from tests.base import TestDimensigonBase


class Test(TestDimensigonBase):

    @patch('dimensigon.web.api_1_0.urls.use_cases.open', mock_open(read_data=b'bibble'))
    @patch('dimensigon.web.api_1_0.urls.use_cases.os.listdir')
    @patch('dimensigon.web.api_1_0.urls.use_cases.current_app')
    def test_software_dimensigon(self, mock_current_app, mock_os):
        type(mock_current_app.dm.config).config_dir = PropertyMock(return_value="/")
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
