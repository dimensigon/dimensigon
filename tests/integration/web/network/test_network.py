import json
from unittest import TestCase

import responses
from aioresponses import CallbackResult, aioresponses
from flask_jwt_extended import create_access_token
from requests import PreparedRequest
from requests.exceptions import ConnectTimeout

from dm.domain.entities import Server, Dimension
from dm.network.auth import HTTPBearerAuth
from dm.utils import asyncio
from dm.utils.asyncio import run
from dm.utils.helpers import generate_dimension
from dm.web import create_app, db
from dm.web.decorators import securizer
from dm.web.network import get, post, async_get, async_post, Response, pack_msg, unpack_msg
from tests.helpers import generate_dimension_json_data

healthcheck_view = 'root.healthcheck'


class TestNetwork(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.json_dim = generate_dimension_json_data()

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')

        @self.app.route('/', methods=['GET', 'POST'])
        def home():
            return {'msg': 'default response'}

        @self.app.route('/securized', methods=['GET', 'POST'])
        @securizer
        def securized():
            return {'msg': 'default response'}

        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.init_app(self.app)
        db.create_all()
        self.server = Server('me', port=5000, me=True)
        db.session.add(self.server)
        db.session.add(Dimension.from_json(self.json_dim))
        db.session.commit()

        self.token = create_access_token('test')
        self.auth = HTTPBearerAuth(self.token)
        self.url = 'http://me:5000/'

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @aioresponses()
    @responses.activate
    def test_get_headers_url_response(self, m):
        msg = {'data': 'content'}
        status = 200

        def callback(request, **kwargs):
            if isinstance(request, PreparedRequest):
                self.assertEqual(str(self.server.id), request.headers.get('D-Destination'))
                self.assertEqual(str(self.server.id), request.headers.get('D-Source'))
                self.assertEqual("True", request.headers.get('D-Securizer'))
                self.assertEqual(f"Bearer {self.token}", request.headers.get('Authorization'))

                return status, {}, json.dumps(msg)
            else:
                self.assertEqual(str(self.server.id), kwargs['headers'].get('D-Destination'))
                self.assertEqual(str(self.server.id), kwargs['headers'].get('D-Source'))
                self.assertEqual("True", kwargs['headers'].get('D-Securizer'))
                self.assertEqual(f"Bearer {self.token}", kwargs['headers'].get('Authorization'))

                return CallbackResult(status=status, payload=msg)

        responses.add_callback(responses.GET, self.url, callback=callback)
        m.get(self.url, callback=callback)

        resp = get(self.server, 'home', auth=self.auth, headers={'D-Securizer': "True"})

        self.assertEqual(
            Response(msg=msg, code=status, exception=None, server=self.server, url=self.url),
            resp)

        resp = run(async_get(self.server, 'home', auth=self.auth, headers={'D-Securizer': "True"}))

        self.assertEqual(
            Response(msg=msg, code=status, exception=None, server=self.server, url=self.url),
            resp)

    @aioresponses()
    @responses.activate
    def test_get_error_json(self, m):
        msg = {'error': 'this is an error message'}
        status = 500
        responses.add(responses.GET, self.url, json=msg, status=status)
        m.get(self.url, payload=msg, status=status)

        resp = get(self.server, 'home')

        self.assertEqual(status, resp.code)
        self.assertDictEqual(msg, resp.msg)

        resp = run(async_get(self.server, 'home'))

        self.assertEqual(status, resp.code)
        self.assertDictEqual(msg, resp.msg)

    @aioresponses()
    @responses.activate
    def test_get_internal_error_server(self, m):
        msg = '<html>Iternal error server</html>'
        status = 500

        responses.add(responses.GET, self.url, status=status, body=msg)
        m.get(self.url, status=status, body=msg)

        resp = get(Server.get_current(), 'home')

        self.assertEqual(status, resp.code)
        self.assertEqual(msg, resp.msg)

        resp = run(async_get(Server.get_current(), 'home'))

        self.assertEqual(status, resp.code)
        self.assertEqual(msg, resp.msg)

    @aioresponses()
    @responses.activate
    def test_post(self, m):
        status = 200
        msg = {'new': 'data'}
        data = {'data': 'some data'}

        def callback(request, **kwargs):
            if isinstance(request, PreparedRequest):
                self.assertDictEqual(data, json.loads(request.body))
                return status, {}, json.dumps(msg)
            else:
                self.assertDictEqual(kwargs['json'], data)
                return CallbackResult(status=status, payload=msg)

        responses.add_callback(responses.POST, self.url, callback=callback)
        m.post(self.url, callback=callback)

        resp = post(self.server, 'home', json=data)

        self.assertEqual(status, resp.code)
        self.assertDictEqual(msg, resp.msg)

        resp = run(async_post(self.server, 'home', json=data))

        self.assertEqual(status, resp.code)
        self.assertDictEqual(msg, resp.msg)

    @aioresponses()
    @responses.activate
    def test_post_no_content_in_response(self, m):
        msg = ''
        status = 204
        responses.add(responses.POST, self.url, status=204)
        m.post(self.url, status=204)

        data, status = post(self.server, 'home')

        self.assertEqual(status, status)
        self.assertEqual(msg, data)

        data, status = run(async_post(self.server, 'home'))

        self.assertEqual(status, status)
        self.assertEqual(msg, data)

    @aioresponses()
    @responses.activate
    def test_connection_error(self, m):
        responses.add(responses.GET, self.url, body=ConnectionError())
        m.get(self.url, exception=ConnectionError())

        resp = get(self.server, 'home')

        self.assertIsNone(resp.code)
        self.assertIsNone(resp.msg)
        self.assertIsInstance(resp.exception, ConnectionError)

        resp = run(async_get(self.server, 'home'))

        self.assertIsNone(resp.code)
        self.assertIsNone(resp.msg)
        self.assertIsInstance(resp.exception, ConnectionError)

    @aioresponses()
    @responses.activate
    def test_timeout(self, m):
        responses.add(responses.GET, self.url, body=ConnectTimeout())
        m.get(self.url, exception=asyncio.TimeoutError())

        resp = get(self.server, 'home', timeout=0.01)

        self.assertIsNone(resp.code)
        self.assertIsNone(resp.msg)
        self.assertIsInstance(resp.exception, TimeoutError)
        self.assertEqual(f"Socket timeout reached while trying to connect to http://me:5000/ "
                         f"for 0.01 seconds", str(resp.exception))

        resp = run(async_get(self.server, 'home', timeout=0.01))

        self.assertIsNone(resp.code)
        self.assertIsNone(resp.msg)
        self.assertIsInstance(resp.exception, TimeoutError)
        self.assertEqual(f"Socket timeout reached while trying to connect to http://me:5000/ "
                         f"for 0.01 seconds", str(resp.exception))

    @aioresponses()
    @responses.activate
    def test_raise_on_error(self, m):
        responses.add(responses.GET, self.url, body=ConnectTimeout())
        m.get(self.url, exception=asyncio.TimeoutError())

        with self.assertRaises(TimeoutError) as e:
            resp = get(self.server, 'home', timeout=1, raise_on_error=True)

        self.assertEqual(f"Socket timeout reached while trying to connect to {Server.get_current().url('root.home')} "
                         f"for 1 seconds", str(e.exception))

        with self.assertRaises(TimeoutError) as e:
            resp = run(
                async_get(self.server, 'home', timeout=1, raise_on_error=True))

        self.assertEqual(f"Socket timeout reached while trying to connect to {Server.get_current().url('root.home')} "
                         f"for 1 seconds", str(e.exception))

    @aioresponses()
    @responses.activate
    def test_raise_on_error_url(self, m):
        responses.add(responses.GET, self.url, body=ConnectTimeout())
        m.get(self.url, exception=asyncio.TimeoutError())

        self.server.gates = []

        with self.assertRaises(RuntimeError) as e:
            resp = get(self.server, 'home', raise_on_error=True)

        resp = get(self.server, 'home')

        self.assertIsInstance(resp.exception, RuntimeError)

        with self.assertRaises(RuntimeError) as e:
            resp = run(
                async_get(self.server, 'home', raise_on_error=True))

        resp = run(
            async_get(self.server, 'home'))

        self.assertIsInstance(resp.exception, RuntimeError)


class TestNetworkSecurizer(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app.config['SECURIZER'] = True

        @self.app.route('/', methods=['GET', 'POST'])
        @securizer
        def home():
            return {'msg': 'default response'}

        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.init_app(self.app)
        db.create_all()
        self.server = Server('me', port=5000, me=True)
        db.session.add(self.server)

        self.dim = generate_dimension('dimension')
        self.dim.current = True
        db.session.add(self.dim)

        self.token = create_access_token('test')
        self.auth = HTTPBearerAuth(self.token)
        self.url = 'http://me:5000/'

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @aioresponses()
    @responses.activate
    def test_get_headers_url_response(self, m):
        msg = {'data': 'content'}
        status = 200

        def callback(request, **kwargs):
            if isinstance(request, PreparedRequest):
                self.assertEqual(str(self.server.id), request.headers.get('D-Destination'))
                self.assertEqual(str(self.server.id), request.headers.get('D-Source'))
                self.assertEqual("True", request.headers.get('D-Securizer'))
                self.assertEqual(f"Bearer {self.token}", request.headers.get('Authorization'))

                return status, {}, json.dumps(pack_msg(msg))
            else:
                self.assertEqual(str(self.server.id), kwargs['headers'].get('D-Destination'))
                self.assertEqual(str(self.server.id), kwargs['headers'].get('D-Source'))
                self.assertEqual("True", kwargs['headers'].get('D-Securizer'))
                self.assertEqual(f"Bearer {self.token}", kwargs['headers'].get('Authorization'))

                return CallbackResult(status=status, payload=pack_msg(msg))

        responses.add_callback(responses.GET, self.url, callback=callback)
        m.get(self.url, callback=callback)

        resp = get(self.server, 'home', auth=self.auth, headers={'D-Securizer': "True"})

        self.assertEqual(
            Response(msg=msg, code=status, exception=None, server=self.server, url=self.url),
            resp)

        resp = run(async_get(self.server, 'home', auth=self.auth, headers={'D-Securizer': "True"}))

        self.assertEqual(
            Response(msg=msg, code=status, exception=None, server=self.server, url=self.url),
            resp)

    @aioresponses()
    @responses.activate
    def test_get_error_json(self, m):
        msg = {'error': 'this is an error message'}
        status = 500
        responses.add(responses.GET, self.url, json=pack_msg(msg), status=status)
        m.get(self.url, payload=pack_msg(msg), status=status)

        resp = get(self.server, 'home')

        self.assertEqual(status, resp.code)
        self.assertDictEqual(msg, resp.msg)

        resp = run(async_get(self.server, 'home'))

        self.assertEqual(status, resp.code)
        self.assertDictEqual(msg, resp.msg)

    @aioresponses()
    @responses.activate
    def test_get_internal_error_server(self, m):
        msg = '<html>Iternal error server</html>'
        status = 500

        responses.add(responses.GET, self.url, status=status, body=msg)
        m.get(self.url, status=status, body=msg)

        resp = get(Server.get_current(), 'home')

        self.assertEqual(status, resp.code)
        self.assertEqual(msg, resp.msg)

        resp = run(async_get(Server.get_current(), 'home'))

        self.assertEqual(status, resp.code)
        self.assertEqual(msg, resp.msg)

    @aioresponses()
    @responses.activate
    def test_post(self, m):
        status = 200
        msg = {'new': 'data'}
        data = {'data': 'some data'}

        def callback(request, **kwargs):
            if isinstance(request, PreparedRequest):
                self.assertDictEqual(data, unpack_msg(json.loads(request.body)))
                return status, {}, json.dumps(pack_msg(msg))
            else:
                self.assertDictEqual(data, unpack_msg(kwargs['json']))
                return CallbackResult(status=status, payload=pack_msg(msg))

        responses.add_callback(responses.POST, self.url, callback=callback)
        m.post(self.url, callback=callback)

        resp = post(self.server, 'home', json=data)

        self.assertEqual(status, resp.code)
        self.assertDictEqual(msg, resp.msg)

        resp = run(async_post(self.server, 'home', json=data))

        self.assertEqual(status, resp.code)
        self.assertDictEqual(msg, resp.msg)

    @aioresponses()
    @responses.activate
    def test_post_no_content_in_response(self, m):
        msg = ''
        status = 204
        responses.add(responses.POST, self.url, status=204)
        m.post(self.url, status=204)

        data, status = post(self.server, 'home')

        self.assertEqual(status, status)
        self.assertEqual(msg, data)

        data, status = run(async_post(self.server, 'home'))

        self.assertEqual(status, status)
        self.assertEqual(msg, data)
