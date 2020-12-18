from unittest import TestCase, mock
from unittest.mock import patch, MagicMock

import requests
import responses
from flask import Flask

from dimensigon.domain.entities import Server, Route
from dimensigon.web import db, errors
from dimensigon.web.decorators import forward_or_dispatch
from tests.base import ValidateResponseMixin


class TestForwardOrDispatch(TestCase, ValidateResponseMixin):

    # def run(self, result=None):
    #     with patch('dimensigon.web.scopefunc') as mock_scopefunc:
    #         mock_scopefunc.side_effect = lambda: threading.get_ident()
    #         super().run(result)

    def setUp(self):
        """Create and configure a new self.app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the self.app with common test config
        self.app = Flask(__name__)

        @self.app.route('/', methods=['GET', 'POST'])
        @forward_or_dispatch()
        def hello():
            return {'msg': 'default response'}

        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.init_app(self.app)
        db.create_all()

        self.srv1 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='server1',
                           dns_or_ip='192.168.1.9', port=7123)
        Route(self.srv1, cost=0)
        self.srv2 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb2', name='server2',
                           dns_or_ip='192.168.1.10', port=7124)
        Route(self.srv2, self.srv1, cost=1)
        db.session.add_all([self.srv1, self.srv2])
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dimensigon.web.decorators.g')
    @responses.activate
    def test_forward_or_dispatch_in_content(self, mock_g):
        mock_g.server = MagicMock(id=self.srv1.id)
        responses.add(responses.POST, 'https://192.168.1.9:7123/', json={'msg': 'response'})

        # check if request is forwarded to the server
        response = self.client.post('/', json={'destination': self.srv2.id, 'data': None})
        self.assertEqual({'msg': 'response'}, response.json)

        self.assertEqual(1, len(responses.calls))
        self.assertEqual('https://192.168.1.9:7123/', responses.calls[0].request.url)

        # check if request is forwarded to the server
        response = self.client.post('/', json={'destination': self.srv1.id, 'data': None})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(1, len(responses.calls))

    @patch('dimensigon.web.decorators.g')
    @responses.activate
    def test_forward_or_dispatch(self, mock_g):
        mock_g.server = MagicMock(id=self.srv1.id)
        responses.add(responses.POST, 'https://192.168.1.9:7123/', json={'msg': 'response'})

        # check if request is forwarded to the server
        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': self.srv2.id})
        self.assertEqual({'msg': 'response'}, response.json)

        self.assertEqual(1, len(responses.calls))
        self.assertEqual('https://192.168.1.9:7123/', responses.calls[0].request.url)

        # check if request is forwarded to the server
        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': self.srv1.id})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(1, len(responses.calls))

    # @patch('dimensigon.web.decorators.g')
    # def test_forward_or_dispatch_hidden_ip(self, mock_g):
    #     mock_g.server = MagicMock(id=self.srv1.id)
    #
    #     response = self.client.post('/', json={'data': None},
    #                                 headers={'D-Destination': self.srv1.id,
    #                                          'D-Source': self.srv2.id},
    #                                 environ_base={'REMOTE_ADDR': '10.1.2.3'})
    #     self.assertEqual({'msg': 'default response'}, response.json)
    #
    #     self.assertEqual(1, len(self.srv2.hidden_gates))
    #     hg = self.srv2.hidden_gates[0]
    #     self.assertEqual('10.1.2.3', str(hg.ip))
    #     self.assertEqual(7124, hg.port)
    #
    #     response = self.client.post('/', json={'data': None},
    #                                 headers={'D-Destination': self.srv1.id,
    #                                          'D-Source': self.srv2.id},
    #                                 environ_base={'REMOTE_ADDR': '10.1.2.3'})
    #     self.assertEqual({'msg': 'default response'}, response.json)
    #
    #     self.assertEqual(1, len(self.srv2.hidden_gates))
    #     self.assertEqual('10.1.2.3', str(hg.ip))
    #     self.assertEqual(7124, hg.port)
    #
    #     response = self.client.post('/', json={'data': None},
    #                                 headers={'D-Destination': self.srv1.id,
    #                                          'D-Source': self.srv2.id},
    #                                 environ_base={'REMOTE_ADDR': '10.1.2.4'})
    #     self.assertEqual({'msg': 'default response'}, response.json)
    #
    #     db.session.refresh(self.srv2)
    #     self.assertEqual(1, len(self.srv2.hidden_gates))
    #     self.assertEqual('10.1.2.4', str(hg.ip))
    #     self.assertEqual(7124, hg.port)

    # @patch('dimensigon.web.decorators.g')
    # def test_forward_or_dispatch_hidden_ip_multiple_ports(self, mock_g):
    #     mock_g.server = MagicMock(id=self.srv1.id)
    #
    #     g = self.srv2.add_new_gate('127.0.0.1', 7125)
    #
    #     db.session.add(g)
    #     db.session.commit()
    #
    #     response = self.client.post('/', json={'data': None},
    #                                 headers={'D-Destination': self.srv1.id,
    #                                          'D-Source': self.srv2.id},
    #                                 environ_base={'REMOTE_ADDR': '10.1.2.3'})
    #
    #     self.assertEqual({'msg': 'default response'}, response.json)
    #
    #     db.session.refresh(self.srv2)
    #
    #     self.assertEqual(2, len(self.srv2.hidden_gates))
    #     hg = self.srv2.hidden_gates
    #     self.assertEqual('10.1.2.3', str(hg[0].ip))
    #     self.assertEqual(7124, hg[0].port)
    #     self.assertEqual('10.1.2.3', str(hg[1].ip))
    #     self.assertEqual(7125, hg[1].port)
    #
    #     response = self.client.post('/', json={'data': None},
    #                                 headers={'D-Destination': self.srv1.id,
    #                                          'D-Source': self.srv2.id},
    #                                 environ_base={'REMOTE_ADDR': '10.1.2.3'})
    #     self.assertEqual({'msg': 'default response'}, response.json)
    #
    #     db.session.refresh(self.srv2)
    #
    #     self.assertEqual(2, len(self.srv2.hidden_gates))
    #     hg = self.srv2.hidden_gates
    #     self.assertEqual('10.1.2.3', str(hg[0].ip))
    #     self.assertEqual(7124, hg[0].port)
    #     self.assertEqual('10.1.2.3', str(hg[1].ip))
    #     self.assertEqual(7125, hg[1].port)
    #
    #     response = self.client.post('/', json={'data': None},
    #                                 headers={'D-Destination': self.srv1.id,
    #                                          'D-Source': self.srv2.id},
    #                                 environ_base={'REMOTE_ADDR': '10.1.2.4'})
    #
    #     self.assertEqual({'msg': 'default response'}, response.json)
    #
    #     db.session.refresh(self.srv2)
    #
    #     self.assertEqual(2, len(self.srv2.hidden_gates))
    #     hg = self.srv2.hidden_gates
    #     self.assertEqual('10.1.2.4', str(hg[0].ip))
    #     self.assertIn(hg[0].port, (7124, 7125))
    #     self.assertEqual('10.1.2.4', str(hg[1].ip))
    #     self.assertIn(hg[1].port, (7124, 7125))

    # @patch('dimensigon.web.decorators.g')
    # def test_forward_or_dispatch_using_proxy_server(self, mock_g):
    #     me = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb0', name='server0',
    #                 dns_or_ip='192.168.1.8', port=7123, me=True)
    #     db.session.add(me)
    #     db.session.commit()
    #     mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb0')
    #
    #     response = self.client.post('/', json={'data': None},
    #                                 headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb0',
    #                                          'D-Source': 'bbbbbbbb-1234-5678-1234-56781234bbb2:bbbbbbbb-1234-5678-1234-56781234bbb1'},
    #                                 environ_base={'REMOTE_ADDR': '192.168.1.9'})
    #     self.assertEqual({'msg': 'default response'}, response.json)
    #
    #     db.session.refresh(self.srv2)
    #     self.assertEqual(0, len(self.srv2.hidden_gates))
    #
    #     response = self.client.post('/', json={'data': None},
    #                                 headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb0',
    #                                          'D-Source': 'bbbbbbbb-1234-5678-1234-56781234bbb2:bbbbbbbb-1234-5678-1234-56781234bbb1'},
    #                                 environ_base={'REMOTE_ADDR': '10.1.2.3'})
    #     self.assertEqual({'msg': 'default response'}, response.json)
    #
    #     db.session.refresh(self.srv1)
    #     self.assertEqual(1, len(self.srv1.hidden_gates))
    #     hg = self.srv1.hidden_gates[0]
    #     self.assertEqual('10.1.2.3', str(hg.ip))
    #     self.assertEqual(7123, hg.port)

    @patch('dimensigon.web.decorators.g')
    def test_server_not_found(self, mock_g):
        mock_g.server = MagicMock(id=self.srv1.id)

        resp = self.client.post('/', json={'data': None},
                                headers={'D-Destination': 'bbbbbbbb-1234-5678-1234-56781234bbb5'})

        self.validate_error_response(resp, errors.EntityNotFound('Server', 'bbbbbbbb-1234-5678-1234-56781234bbb5'))

    @patch('dimensigon.web.decorators.socket.gethostbyname')
    @patch('dimensigon.web.decorators.g')
    def test_forward_or_dispatch_dns(self, mock_g, mock_gethostbyname):
        mock_g.server = MagicMock(id=self.srv1.id)

        def gethostbyname(dns: str):
            if dns == 'server2':
                return '10.1.2.3'
            else:
                return None

        mock_gethostbyname.side_effect = gethostbyname
        self.srv2.add_new_gate('server2', 7124)
        db.session.commit()

        response = self.client.post('/', json={'data': None},
                                    headers={'D-Destination': self.srv1.id,
                                             'D-Source': self.srv2.id},
                                    environ_base={'REMOTE_ADDR': '10.1.2.3'})
        self.assertEqual({'msg': 'default response'}, response.json)

        self.assertEqual(0, len(self.srv2.hidden_gates))

    @patch('dimensigon.web.decorators.requests.request', autospec=True)
    @patch('dimensigon.web.decorators.g')
    def test_forward_or_dispatch_proxy_request(self, mock_g, mock_request):
        mock_g.server = MagicMock(id=self.srv1.id)

        def request(*args, **kwargs):
            r = requests.Response()
            r._content = kwargs['headers'].get('d-source')
            r.status_code = 222
            return r

        mock_request.side_effect = request

        # check if request is forwarded to the server without d-source header
        resp = self.client.post('/', json={'data': None},
                                headers={'D-Destination': self.srv2.id})

        self.assertEqual(':bbbbbbbb-1234-5678-1234-56781234bbb1', resp.get_data(True))

        # check if request is forwarded to the server with d-source header
        resp = self.client.post('/', json={'data': None},
                                headers={'D-Destination': self.srv2.id,
                                         'D-Source': 'bbbbbbbb-1234-5678-1234-56781234bbb0'})

        self.assertEqual('bbbbbbbb-1234-5678-1234-56781234bbb0:bbbbbbbb-1234-5678-1234-56781234bbb1',
                             resp.get_data(True))

    @patch('dimensigon.web.decorators.g')
    def test_forward_or_dispatch_unreachable_destination(self, mock_g):
        type(mock_g).server = mock.PropertyMock(return_value=self.srv1)
        self.srv2.set_route(None, None, None)
        resp = self.client.post('/', json={'data': None},
                            headers={'D-Destination': self.srv2.id})

        self.validate_error_response(resp, errors.UnreachableDestination(self.srv2, self.srv1))

    @patch('dimensigon.web.decorators.requests.request', autospec=True)
    @patch('dimensigon.web.decorators.g')
    def test_forward_or_dispatch_error_proxying(self, mock_g, mock_request):
        mock_g.server = MagicMock(id=self.srv1.id)
        mock_request.side_effect = requests.exceptions.ConnectionError('error')

        # check if request is forwarded to the server
        resp = self.client.post('/', json={'data': None},
                                headers={'D-Destination': self.srv2.id})

        self.validate_error_response(resp, errors.ProxyForwardingError(self.srv2,
                                                                       requests.exceptions.ConnectionError('error')))
