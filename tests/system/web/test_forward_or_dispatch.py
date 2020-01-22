import io
import json
from unittest import TestCase, mock

import requests
from flask import url_for

import config
from dm.domain.entities import Dimension, Server
from dm.web import create_app, db, set_variables
from dm.web.errors import UnknownServer
from tests.helpers import initial_test_data


class TestForwardOrDispatch(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the app with common test config
        config.TestingConfig.SERVER_NAME = 'server1.localdomain'
        self.app = create_app(config.TestingConfig)

        with self.app.app_context():
            db.create_all()
            # with session_scope() as s:
            srv1 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='server1.localdomain',
                          ip='192.168.1.9', port=7123)
            srv2 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb2', name='server2.localdomain', ip='192.168.1.10',
                          port=7124)
            db.session.add_all([srv1, srv2])
            db.session.commit()
            set_variables()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.drop_all()

    def test_forward_or_dispatch(self):
        with mock.patch('dm.network.gateway.requests.request') as mocked_post:
            with self.app.app_context():
                server1 = Server.query.get('bbbbbbbb-1234-5678-1234-56781234bbb1')
                server2 = Server.query.get('bbbbbbbb-1234-5678-1234-56781234bbb2')
                resp = requests.Response()
                resp.url = server2.url('root.healthcheck', data_mark='20190101000529100000')
                resp.headers = {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json'}
                resp.status_code = 200
                resp._content = 'response'
                resp.raw = io.BytesIO(b"some content")
                mocked_post.return_value = resp


                # check if request is forwarded to the server
                client = self.app.test_client()
                response = client.post(url_for('root.healthcheck', data_mark='20190101000529100000', _external=False),
                                       json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2', 'data': None})
                data = {'data': None, 'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2'}
                kwargs = {'stream': True,
                          'json': data,
                          'allow_redirects': False,
                          'headers': {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json',
                                      'CONTENT-LENGTH': str(len(str(data)))},
                          'cookies': {}}
                mocked_post.assert_called_once_with('POST',
                                                    server2.url('root.healthcheck', data_mark='20190101000529100000'),
                                                    **kwargs)

    def test_server_not_found(self):
        with self.app.app_context():
            # check if request is forwarded to the server
            client = self.app.test_client()
            response = client.post(url_for('root.healthcheck', data_mark='20190101000529100000', _external=False),
                                   json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb5', 'data': None})
            self.assertDictEqual(UnknownServer('bbbbbbbb-1234-5678-1234-56781234bbb5')._format_error_msg(),
                                 response.get_json())


    def test_forward_or_dispatch_in_header(self):
        with mock.patch('dm.network.gateway.requests.request') as mocked_post:
            with self.app.app_context():
                server1 = Server.query.get('bbbbbbbb-1234-5678-1234-56781234bbb1')
                server2 = Server.query.get('bbbbbbbb-1234-5678-1234-56781234bbb2')
                resp = requests.Response()
                resp.url = server2.url('root.healthcheck', data_mark='20190101000529100000')
                resp.headers = {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json'}
                resp.status_code = 200
                resp._content = 'response'
                resp.raw = io.BytesIO(b"some content")
                mocked_post.return_value = resp


                # check if request is forwarded to the server
                client = self.app.test_client()
                response = client.post(url_for('root.healthcheck', data_mark='20190101000529100000', _external=False),
                                       json={},  headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2'})

                kwargs = {'stream': True,
                          'json': {},
                          'allow_redirects': False,
                          'headers': {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json',
                                      'CONTENT-LENGTH': str(len(str({}))), 'D-DESTINATION': 'bbbbbbbb-1234-5678-1234-56781234bbb2'},
                          'cookies': {}}
                mocked_post.assert_called_once_with('POST',
                                                    server2.url('root.healthcheck', data_mark='20190101000529100000'),
                                                    **kwargs)