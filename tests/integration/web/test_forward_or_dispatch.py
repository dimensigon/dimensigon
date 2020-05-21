from unittest import TestCase
from unittest.mock import patch, MagicMock

import responses
from flask import Flask

from dm.domain.entities import Server, Route
from dm.web import db
from dm.web.decorators import forward_or_dispatch
from dm.web.errors import UnknownServer

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
@forward_or_dispatch
def hello():
    return {'msg': 'default response'}


class TestForwardOrDispatch(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the app with common test config
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()
        db.init_app(app)
        db.create_all()

        self.srv1 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='server1',
                           dns_or_ip='192.168.1.9', port=7123)
        Route(self.srv1, cost=0)
        self.srv2 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb2', name='server2',
                           dns_or_ip='192.168.1.10', port=7124)
        Route(self.srv2, proxy_server=self.srv1, cost=1)
        db.session.add_all([self.srv1, self.srv2])
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dm.web.decorators.g')
    @responses.activate
    def test_forward_or_dispatch(self, mock_g):
        mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')
        responses.add(responses.POST, 'http://192.168.1.9:7123/', json={'msg': 'response'})

        # check if request is forwarded to the server
        response = self.client.post('/', json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2', 'data': None})
        self.assertEqual({'msg': 'response'}, response.json)

        self.assertEqual(1, len(responses.calls))
        self.assertEqual('http://192.168.1.9:7123/', responses.calls[0].request.url)

        # check if request is forwarded to the server
        response = self.client.post('/', json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb1', 'data': None})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(1, len(responses.calls))

    @patch('dm.web.decorators.g')
    def test_server_not_found(self, mock_g):
        mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')

        response = self.client.post('/', json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb5', 'data': None})
        self.assertDictEqual(UnknownServer('bbbbbbbb-1234-5678-1234-56781234bbb5')._format_error_msg(),
                             response.json)

    @patch('dm.web.decorators.g')
    @responses.activate
    def test_forward_or_dispatch(self, mock_g):
        mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')
        responses.add(responses.POST, 'http://192.168.1.9:7123/', json={'msg': 'response'})

        # check if request is forwarded to the server
        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2'})
        self.assertEqual({'msg': 'response'}, response.json)

        self.assertEqual(1, len(responses.calls))
        self.assertEqual('http://192.168.1.9:7123/', responses.calls[0].request.url)

        # check if request is forwarded to the server
        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb1'})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(1, len(responses.calls))

    @patch('dm.web.decorators.g')
    def test_forward_or_dispatch_hidden_ip(self, mock_g):
        mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')

        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb1',
                                             'D-Source': 'bbbbbbbb-1234-5678-1234-56781234bbb2'},
                                    environ_base={'REMOTE_ADDR': '10.1.2.3'})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(1, len(self.srv2.hidden_gates))
        hg = self.srv2.hidden_gates[0]
        self.assertEqual('10.1.2.3', str(hg.ip))
        self.assertEqual(7124, hg.port)

        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb1',
                                             'D-Source': 'bbbbbbbb-1234-5678-1234-56781234bbb2'},
                                    environ_base={'REMOTE_ADDR': '10.1.2.3'})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(1, len(self.srv2.hidden_gates))
        self.assertEqual('10.1.2.3', str(hg.ip))
        self.assertEqual(7124, hg.port)


        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb1',
                                             'D-Source': 'bbbbbbbb-1234-5678-1234-56781234bbb2'},
                                    environ_base={'REMOTE_ADDR': '10.1.2.4'})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(1, len(self.srv2.hidden_gates))
        self.assertEqual('10.1.2.4', str(hg.ip))
        self.assertEqual(7124, hg.port)


    @patch('dm.web.decorators.g')
    def test_forward_or_dispatch_hidden_ip_multiple_ports(self, mock_g):
        mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')

        self.srv2.add_new_gate('127.0.0.1', 7125)

        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb1',
                                             'D-Source': 'bbbbbbbb-1234-5678-1234-56781234bbb2'},
                                    environ_base={'REMOTE_ADDR': '10.1.2.3'})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(2, len(self.srv2.hidden_gates))
        hg = self.srv2.hidden_gates
        self.assertEqual('10.1.2.3', str(hg[0].ip))
        self.assertEqual(7124, hg[0].port)
        self.assertEqual('10.1.2.3', str(hg[1].ip))
        self.assertEqual(7125, hg[1].port)

        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb1',
                                             'D-Source': 'bbbbbbbb-1234-5678-1234-56781234bbb2'},
                                    environ_base={'REMOTE_ADDR': '10.1.2.3'})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(2, len(self.srv2.hidden_gates))
        hg = self.srv2.hidden_gates
        self.assertEqual('10.1.2.3', str(hg[0].ip))
        self.assertEqual(7124, hg[0].port)
        self.assertEqual('10.1.2.3', str(hg[1].ip))
        self.assertEqual(7125, hg[1].port)

        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb1',
                                             'D-Source': 'bbbbbbbb-1234-5678-1234-56781234bbb2'},
                                    environ_base={'REMOTE_ADDR': '10.1.2.4'})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(2, len(self.srv2.hidden_gates))
        hg = self.srv2.hidden_gates
        self.assertEqual('10.1.2.4', str(hg[0].ip))
        self.assertIn(hg[0].port, (7124, 7125))
        self.assertEqual('10.1.2.4', str(hg[1].ip))
        self.assertIn(hg[1].port, (7124, 7125))

    @patch('dm.web.decorators.socket.gethostbyname')
    @patch('dm.web.decorators.g')
    def test_forward_or_dispatch_dns(self, mock_g, mock_gethostbyname):
        mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')

        def gethostbyname(dns: str):
            if dns == 'server2':
                return '10.1.2.3'
            else:
                return None
        mock_gethostbyname.side_effect = gethostbyname
        self.srv2.add_new_gate('server2', 7124)

        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb1',
                                             'D-Source': 'bbbbbbbb-1234-5678-1234-56781234bbb2'},
                                    environ_base={'REMOTE_ADDR': '10.1.2.3'})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(0, len(self.srv2.hidden_gates))