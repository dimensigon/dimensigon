from unittest import TestCase, mock
from unittest.mock import patch

import requests
import rsa
from click.testing import CliRunner

from wsgi import join


class TestWsgi(TestCase):
    def setUp(self) -> None:
        self.pub_key, self.priv_key = rsa.newkeys(256)

    @mock.patch("wsgi.requests.post")
    @mock.patch("wsgi.open", create=True)
    def test_join(self, mock_open, mock_post):
        mock_open.side_effect = [
            mock.mock_open(read_data=self.pub_key.save_pkcs1()).return_value
        ]

        resp = requests.Response()
        resp.status_code = 400
        mock_post.return_value = resp

        runner = CliRunner(env={'FLASK_APP': r"G:\Mi unidad\Projects\DimenSigon\dimensigon\dm\web:create_app('dev')",
                                'FLASK_ENV': 'dev'})
        # runner = app.test_cli_runner()
        result = runner.invoke(join, ['localhost:5002', 'token'])
        print('Output: ', result.stdout)
        self.assertEqual(0, result.exit_code)
