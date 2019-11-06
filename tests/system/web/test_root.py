from unittest import TestCase, mock

import requests

from dm.web import create_app


class TestRoot(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the app with common test config
        self.app = create_app('dev')

        # # create the database and load test data
        # with app.app_context():
        #     init_db()
        #     get_db().executescript(_data_sql)

    def tearDown(self) -> None:
        pass
        # # close and remove the temporary database
        # os.close(db_fd)
        # os.unlink(db_path)

    def test_healthcheck(self):
        client = self.app.test_client()
        response = client.get('/healthcheck')

        self.assertDictEqual({"version": "0.0.1",
                              "elevator_version": "0.0.1",
                              "catalog_version": "20190101000530100000",
                              "neighbours": [],
                              "services": [
                                  {
                                      "service1": {
                                          "status": "ALIVE"
                                      }
                                  }
                              ]
                              }, response.get_json())

    def test_forward_or_dispatch(self, ):
        with mock.patch('dm.network.gateway.requests.request') as mocked_post:
            resp = requests.Response()
            resp.url = 'http://server1.localdomain:80/socket?'
            resp.headers = {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json'}
            resp.status_code = 200
            resp._content = ''
            mocked_post.return_value = resp

            # check if request is forwarded to the server
            client = self.app.test_client()
            response = client.post('/socket',
                                   json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2', 'data': None})
            data = {'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2', 'data': None}
            kwargs = {'json': data,
                      'allow_redirects': False,
                      'headers': {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json',
                                  'CONTENT-LENGTH': str(len(str(data)))}}
            mocked_post.assert_called_once_with('POST', resp.url, **kwargs)

        with mock.patch('dm.web.routes.dispatch_message') as mocked_dispatch_message:
            mocked_dispatch_message.return_value = ''
            response = client.post('/socket',
                                   json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb1', 'data': None})
            mocked_dispatch_message.assert_called_once_with(None, self.app.extensions['interactor']._mediator)
