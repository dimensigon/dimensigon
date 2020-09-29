from unittest import TestCase
from unittest.mock import patch

from flask import Flask

from dimensigon.domain.entities import Server, Route
from dimensigon.network.exceptions import NotValidMessage
from dimensigon.utils.helpers import generate_dimension
from dimensigon.web import db
from dimensigon.web.decorators import securizer


class TestSecurizer(TestCase):
    def setUp(self):
        """Create and configure a new self.app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the self.app with common test config

        self.app = Flask(__name__)

        @self.app.route('/', methods=['GET', 'POST'])
        @securizer
        def hello():
            return {'msg': 'default response'}

        self.app.config['SECURIZER_PLAIN'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.init_app(self.app)
        db.create_all()
        self.d = generate_dimension('test')
        self.srv1 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='server1',
                           dns_or_ip='192.168.1.9', port=7123, me=True)
        Route(self.srv1, cost=0)

        db.session.add_all([self.srv1, self.d])
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dimensigon.web.decorators.url_for')
    @patch('dimensigon.web.decorators.pack_msg')
    def test_get_securizer(self, mock_pack_msg, mock_url_for):
        # mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')
        mock_pack_msg.return_value = {'data': 'encrypted data'}
        mock_url_for.return_value = '/join'

        resp = self.client.get('/')

        self.assertEqual(200, resp.status_code)
        mock_pack_msg.assert_called_once_with(data={'msg': 'default response'})
        self.assertDictEqual({'data': 'encrypted data'}, resp.get_json())

        resp = self.client.get('/', headers={'D-Securizer': 'plain'})

        self.assertEqual(200, resp.status_code)
        mock_pack_msg.assert_called_once()
        self.assertDictEqual({'msg': 'default response'}, resp.get_json())

    @patch('dimensigon.web.decorators.url_for')
    @patch('dimensigon.web.decorators.pack_msg')
    def test_get_securizer_plain_not_allowed(self, mock_pack_msg, mock_url_for):
        # mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')
        mock_pack_msg.return_value = {'data': 'encrypted data'}
        mock_url_for.return_value = '/join'
        self.app.config['SECURIZER_PLAIN'] = False
        resp = self.client.get('/', headers={'D-Securizer': 'plain'})

        self.assertEqual(406, resp.status_code)
        mock_pack_msg.assert_not_called()
        self.assertDictEqual({'error': 'plain data is not allowed'}, resp.get_json())

    @patch('dimensigon.web.decorators.url_for')
    @patch('dimensigon.web.decorators.unpack_msg')
    @patch('dimensigon.web.decorators.pack_msg')
    def test_post_securizer(self, mock_pack_msg, mock_unpack_msg, mock_url_for):
        # mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')
        mock_pack_msg.return_value = {'data': 'encrypted data'}
        mock_unpack_msg.return_value = {'data': 'decrypted data'}
        mock_url_for.return_value = '/join'
        resp = self.client.post('/', json={'data': 'post data'})

        self.assertEqual(200, resp.status_code)
        mock_unpack_msg.assert_called_once_with(data={'data': 'post data'})
        mock_pack_msg.assert_called_once_with(data={'msg': 'default response'})
        self.assertDictEqual({'data': 'encrypted data'}, resp.get_json())

        resp = self.client.post('/', json={'data': 'post data'}, headers={'D-Securizer': 'plain'})

        self.assertEqual(200, resp.status_code)
        mock_unpack_msg.assert_called_once()
        mock_pack_msg.assert_called_once()
        self.assertDictEqual({'msg': 'default response'}, resp.get_json())

    @patch('dimensigon.web.decorators.url_for')
    @patch('dimensigon.web.decorators.unpack_msg')
    @patch('dimensigon.web.decorators.pack_msg')
    def test_post_securizer_plain_not_allowed(self, mock_pack_msg, mock_unpack_msg, mock_url_for):
        # mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')
        mock_pack_msg.return_value = {'data': 'encrypted data'}
        mock_url_for.return_value = '/join'
        self.app.config['SECURIZER_PLAIN'] = False
        resp = self.client.post('/', json={'data': 'post data'}, headers={'D-Securizer': 'plain'})


        self.assertEqual(406, resp.status_code)

        mock_unpack_msg.assert_not_called()
        mock_pack_msg.assert_not_called()
        self.assertDictEqual({'error': 'plain data is not allowed'}, resp.get_json())

    @patch('dimensigon.web.decorators.url_for')
    @patch('dimensigon.web.decorators.unpack_msg')
    @patch('dimensigon.web.decorators.pack_msg')
    def test_post_securizer_validation_error(self, mock_pack_msg, mock_unpack_msg, mock_url_for):
        # mock_g.server = MagicMock(id='bbbbbbbb-1234-5678-1234-56781234bbb1')

        mock_url_for.return_value = '/join'
        mock_unpack_msg.side_effect = NotValidMessage("Message")

        resp = self.client.post('/', json={'data': 'post data'})


        self.assertEqual(400, resp.status_code)
        self.assertDictEqual({'error': 'Message',
                                'message': {'data': 'post data'}}, resp.get_json())

        mock_unpack_msg.assert_called_once_with(data={'data': 'post data'})
        mock_pack_msg.assert_not_called()