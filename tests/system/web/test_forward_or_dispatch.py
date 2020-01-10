import io
import json
from unittest import TestCase, mock

import requests
from flask import url_for

from dm.domain.entities import Dimension, Server
from dm.web import create_app, db, set_variables
from dm.web.errors import UnknownServer
from tests.helpers import initial_test_data


class TestForwardOrDispatch(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the app with common test config
        self.app = create_app('test')

        with self.app.app_context():
            db.create_all()
            # with session_scope() as s:
            srv1 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='localhost.localdomain',
                          ip='127.0.0.1', port=7123)
            srv2 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb2', name='server1.localdomain', ip='127.0.0.1',
                          port=7124)
            db.session.add_all([srv1, srv2])
            db.session.commit()
            set_variables()
            self.url = url_for('root.healthcheck', data_mark='20190101000529100000', _scheme='https')

    def tearDown(self) -> None:
        with self.app.app_context():
            db.drop_all()

    def test_forward_or_dispatch(self):
        with mock.patch('dm.network.gateway.requests.request') as mocked_post:
            resp = requests.Response()
            resp.url = self.url
            resp.headers = {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json'}
            resp.status_code = 200
            resp._content = 'response'
            resp.raw = io.BytesIO(b"some content")
            mocked_post.return_value = resp

            # check if request is forwarded to the server
            client = self.app.test_client()
            response = client.post(self.url,
                                   json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2', 'data': None})
            data = {'data': None, 'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2'}
            kwargs = {'stream': True,
                      'json': data,
                      'allow_redirects': False,
                      'headers': {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json',
                                  'CONTENT-LENGTH': str(len(str(data)))},
                      'cookies': {}}
            mocked_post.assert_called_once_with('POST', resp.url.replace('localhost.localdomain', 'server1.localdomain:7124'), **kwargs)

    def test_server_not_found(self):
        # check if request is forwarded to the server
        client = self.app.test_client()
        response = client.post(self.url,
                               json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb5', 'data': None})
        self.assertDictEqual(UnknownServer('bbbbbbbb-1234-5678-1234-56781234bbb5')._format_error_msg(), response.get_json())