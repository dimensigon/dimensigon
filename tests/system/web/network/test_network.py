import json
import re
from functools import partial
from unittest import TestCase

import aiohttp
import responses
from aioresponses import CallbackResult, aioresponses
from flask_jwt_extended import create_access_token

from dm.domain.entities import Server, ActionTemplate, ActionType
from dm.domain.entities.bootstrap import set_initial
from dm.utils.asyncio import run
from dm.utils.helpers import generate_dimension
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth, get, post, async_get, async_post

healthcheck_view = 'root.healthcheck'


class TestNetwork(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.token = create_access_token('test')
        self.auth = HTTPBearerAuth(self.token)
        self.headers = dict(Authorization=f"Bearer {self.token}")
        db.create_all()
        set_initial()
        dim = generate_dimension('dimension')
        dim.current = True
        at = ActionTemplate(id='12345678-1234-5678-1234-567812345678',
                            name='rmdir', version=1, action_type=ActionType.NATIVE, code='rmdir {dir}')

        db.session.add_all([dim, at])
        db.session.commit()
        self.at_json = at.to_json()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @responses.activate
    def test_get_error(self):
        def requests_callback_client(client, request):
            self.assertIn('d-destination', request.headers)
            self.assertIn('d-source', request.headers)
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return 500, resp.headers, "some error data"

        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(),
                   'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']),
                   auth=self.auth
                   )

        self.assertEqual("some error data", resp[0])

    @responses.activate
    def test_get_error_json(self):
        def requests_callback_client(client, request):
            self.assertIn('d-destination', request.headers)
            self.assertIn('d-source', request.headers)
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return 500, resp.headers, json.dumps({'error': 'this is an error message'})

        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(),
                   'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']),
                   auth=self.auth
                   )

        self.assertDictEqual({'error': 'this is an error message'}, resp[0])

    @responses.activate
    def test_get_error_json2(self):
        def requests_callback_client(client, request):
            self.assertIn('d-destination', request.headers)
            self.assertIn('d-source', request.headers)
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return 500, resp.headers, json.dumps({'msg': 'this is an error message'})

        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(),
                   'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']),
                   auth=self.auth
                   )

        self.assertDictEqual({'msg': 'this is an error message'}, resp[0])

    @responses.activate
    def test_get(self):
        def requests_callback_client(client, request):
            self.assertIn('d-destination', request.headers)
            self.assertIn('d-source', request.headers)
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(),
                   'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']),
                   auth=self.auth
                   )

        self.assertDictEqual(self.at_json, resp[0])

    @responses.activate
    def test_post(self):
        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))
        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        data = dict(name='action', version=1, action_type='NATIVE', code='None')
        resp = post(Server.get_current(), 'api_1_0.actiontemplatelist', json=data,
                    auth=self.auth)

        self.assertIn('action_template_id', resp[0])

    @responses.activate
    def test_get_securizer_error(self):
        self.app.config['SECURIZER'] = True

        def requests_callback_client(client, request):
            self.assertIn('d-destination', request.headers)
            self.assertIn('d-source', request.headers)
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return 500, resp.headers, "some error data"

        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(),
                   'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']),
                   auth=self.auth
                   )

        self.assertEqual("some error data", resp[0])

    @responses.activate
    def test_get_securizer(self):
        self.app.config['SECURIZER'] = True

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))
        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(), 'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']), auth=self.auth)

        self.assertIn('version', resp[0])

    @responses.activate
    def test_post_securizer(self):
        self.app.config['SECURIZER'] = True

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))
        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        data = dict(name='action', version=1, action_type='NATIVE', code='None')
        resp = post(Server.get_current(), 'api_1_0.actiontemplatelist', json=data,
                    auth=self.auth)

        self.assertIn('action_template_id', resp[0])

    @responses.activate
    def test_get_internal_error_server(self):
        self.app.config['SECURIZER'] = True

        responses.add(responses.GET, re.compile('https?://127\.0\.0\.1.*'), status=500,
                      body='<html>Iternal error server</html>')

        data, status = get(Server.get_current(), healthcheck_view, auth=self.auth)

        self.assertEqual(500, status)
        self.assertEqual('<html>Iternal error server</html>', data)

    @responses.activate
    def test_post_securizer(self):
        self.app.config['SECURIZER'] = True

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1.*'),
                               callback=partial(requests_callback_client, self.client))

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json, auth=self.auth)

        self.assertIn('action_template_id', data)

    @responses.activate
    def test_post_no_content_in_response(self):
        self.app.config['SECURIZER'] = True

        def callback_post_client(request):
            return 200, dict(content_type='text/html'), ''

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json, auth=self.auth)

        self.assertEqual(200, status)
        self.assertEqual('', data)

    @responses.activate
    def test_post_no_data_content_type(self):
        self.app.config['SECURIZER'] = True

        def callback_post_client(request):
            self.assertEqual('application/json', request.headers.get('content-type'))
            return 200, dict(content_type='text/html'), ''

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client)

        data, status = post(Server.get_current(), 'api_1_0.actiontemplatelist', auth=self.auth)

    @responses.activate
    def test_post_connection_error(self):
        self.app.config['SECURIZER'] = True

        responses.add(responses.POST, re.compile('https?://127\.0\.0\.1.*'), body=ConnectionError())

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json, auth=self.auth)

        self.assertEqual(None, status)
        self.assertIsInstance(data, ConnectionError)

    @aioresponses()
    def test_async_get_internal_error_server(self, m):
        self.app.config['SECURIZER'] = True

        m.get(re.compile('https?://127\.0\.0\.1.*'), status=500, body='<html>Iternal error server</html>')

        data, status = run(
            async_get(Server.get_current(), healthcheck_view, auth=self.auth))

        self.assertEqual(500, status)
        self.assertEqual('<html>Iternal error server</html>', data)

    @aioresponses()
    def test_async_post_securizer(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.post(url.path, json=kwargs['json'], headers=self.headers)

            return CallbackResult('POST', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertIn('action_template_id', data)

    @aioresponses()
    def test_async_post_no_content_in_response(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            return CallbackResult('POST', status=200, body='', content_type='text/html')

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertEqual(200, status)
        self.assertEqual('', data)

    @aioresponses()
    def test_async_post_no_data_content_type(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            self.assertEqual('application/json', kwargs.get('headers').get('content-type'))
            return CallbackResult('POST', status=200, body='', content_type='text/html')

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', auth=self.auth))

    @aioresponses()
    def test_async_post_connection_error(self, m):
        self.app.config['SECURIZER'] = True

        m.post(re.compile('https?://127\.0\.0\.1.*'), exception=aiohttp.ClientConnectionError())

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertEqual(None, status)
        self.assertIsInstance(data, aiohttp.ClientConnectionError)

    @aioresponses()
    def test_async_get_error(self, m):
        def callback_get_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=500, body="some error data", content_type='text/html',
                                  headers=r.headers)

        m.get(re.compile('https?://127\.0\.0\.1.*'), callback=callback_get_client, repeat=True)

        data, status = run(async_get(Server.get_current(),
                                     'api_1_0.actiontemplateresource',
                                     view_data=dict(
                                         action_template_id=self.at_json['id']),
                                     auth=self.auth
                                     ))

        self.assertEqual("some error data", data)

    @aioresponses()
    def test_async_get_json_error(self, m):
        def callback_get_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=500, body='{"error":"this is an error message"}',
                                  content_type='application/json',
                                  headers=r.headers)

        m.get(re.compile('https?://127\.0\.0\.1.*'), callback=callback_get_client, repeat=True)

        data, status = run(async_get(Server.get_current(),
                                     'api_1_0.actiontemplateresource',
                                     view_data=dict(
                                         action_template_id=self.at_json['id']),
                                     auth=self.auth
                                     ))

        self.assertDictEqual({"error": "this is an error message"}, data)

    @aioresponses()
    def test_async_get(self, m):
        def callback_get_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.get(re.compile('https?://127\.0\.0\.1.*'), callback=callback_get_client, repeat=True)

        data, status = run(async_get(Server.get_current(),
                                     'api_1_0.actiontemplateresource',
                                     view_data=dict(
                                         action_template_id=self.at_json['id']),
                                     auth=self.auth
                                     ))

        self.assertDictEqual(self.at_json, data)

    @aioresponses()
    def test_async_post(self, m):
        def callback_post_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.post(url.path, json=kwargs['json'], headers=self.headers)

            return CallbackResult('POST', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertIn('action_template_id', data)

    @aioresponses()
    def test_async_get_securizer_error(self, m):
        def callback_get_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=500, body="some error data", content_type='text/html',
                                  headers=r.headers)

        m.get(re.compile('https?://127\.0\.0\.1.*'), callback=callback_get_client, repeat=True)

        data, status = run(async_get(Server.get_current(),
                                     'api_1_0.actiontemplateresource',
                                     view_data=dict(
                                         action_template_id=self.at_json['id']),
                                     auth=self.auth
                                     ))

        self.assertEqual("some error data", data)

    @aioresponses()
    def test_async_get_securizer(self, m):
        self.app.config['SECURIZER'] = True

        def callback_get_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.get(re.compile('https?://127\.0\.0\.1.*'), callback=callback_get_client, repeat=True)

        data, status = run(
            async_get(Server.get_current(), 'api_1_0.actiontemplateresource',
                      view_data=dict(action_template_id=self.at_json['id']), auth=self.auth))

        self.assertIn('version', data)

    @aioresponses()
    def test_async_get_internal_error_server(self, m):
        self.app.config['SECURIZER'] = True

        m.get(re.compile('https?://127\.0\.0\.1.*'), status=500, body='<html>Iternal error server</html>')

        data, status = run(
            async_get(Server.get_current(), healthcheck_view, auth=self.auth))

        self.assertEqual(500, status)
        self.assertEqual('<html>Iternal error server</html>', data)

    @aioresponses()
    def test_async_post_securizer(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.post(url.path, json=kwargs['json'], headers=self.headers)

            return CallbackResult('POST', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertIn('action_template_id', data)

    @aioresponses()
    def test_async_post_no_content_in_response(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            return CallbackResult('POST', status=200, body='', content_type='text/html')

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertEqual(200, status)
        self.assertEqual('', data)

    @aioresponses()
    def test_async_post_no_data_content_type(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            self.assertEqual('application/json', kwargs.get('headers').get('content-type'))
            return CallbackResult('POST', status=200, body='', content_type='text/html')

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', auth=self.auth))

    @aioresponses()
    def test_async_post_connection_error(self, m):
        self.app.config['SECURIZER'] = True

        m.post(re.compile('https?://127\.0\.0\.1.*'), exception=aiohttp.ClientConnectionError())

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertEqual(None, status)
        self.assertIsInstance(data, aiohttp.ClientConnectionError)


class TestNetworkWithSecurizer(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app.config['SECURIZER'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.token = create_access_token('test')
        self.auth = HTTPBearerAuth(self.token)
        self.headers = dict(Authorization=f"Bearer {self.token}")
        db.create_all()
        set_initial()
        dim = generate_dimension('dimension')
        dim.current = True
        at = ActionTemplate(id='12345678-1234-5678-1234-567812345678',
                            name='rmdir', version=1, action_type=ActionType.NATIVE, code='rmdir {dir}')

        db.session.add_all([dim, at])
        db.session.commit()
        self.at_json = at.to_json()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @responses.activate
    def test_get_error(self):
        def requests_callback_client(client, request):
            self.assertIn('d-destination', request.headers)
            self.assertIn('d-source', request.headers)
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return 500, resp.headers, "some error data"

        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(),
                   'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']),
                   auth=self.auth
                   )

        self.assertEqual("some error data", resp[0])

    @responses.activate
    def test_get_error_json(self):
        def requests_callback_client(client, request):
            self.assertIn('d-destination', request.headers)
            self.assertIn('d-source', request.headers)
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return 500, resp.headers, json.dumps({'error': 'this is an error message'})

        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(),
                   'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']),
                   auth=self.auth
                   )

        self.assertDictEqual({'error': 'this is an error message'}, resp[0])

    @responses.activate
    def test_get_error_json2(self):
        def requests_callback_client(client, request):
            self.assertIn('d-destination', request.headers)
            self.assertIn('d-source', request.headers)
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return 500, resp.headers, json.dumps({'msg': 'this is an error message'})

        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(),
                   'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']),
                   auth=self.auth
                   )

        self.assertDictEqual({'msg': 'this is an error message'}, resp[0])

    @responses.activate
    def test_get(self):
        def requests_callback_client(client, request):
            self.assertIn('d-destination', request.headers)
            self.assertIn('d-source', request.headers)
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))
        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(),
                   'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']),
                   auth=self.auth
                   )

        self.assertDictEqual(self.at_json, resp[0])

    @responses.activate
    def test_post(self):
        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))
        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        data = dict(name='action', version=1, action_type='NATIVE', code='None')
        resp = post(Server.get_current(), 'api_1_0.actiontemplatelist', json=data,
                    auth=self.auth)

        self.assertIn('action_template_id', resp[0])

    @responses.activate
    def test_get_securizer_error(self):
        self.app.config['SECURIZER'] = True

        def requests_callback_client(client, request):
            self.assertIn('d-destination', request.headers)
            self.assertIn('d-source', request.headers)
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return 500, resp.headers, "some error data"

        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(),
                   'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']),
                   auth=self.auth
                   )

        self.assertEqual("some error data", resp[0])

    @responses.activate
    def test_get_securizer(self):
        self.app.config['SECURIZER'] = True

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))
        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        resp = get(Server.get_current(), 'api_1_0.actiontemplateresource',
                   view_data=dict(action_template_id=self.at_json['id']), auth=self.auth)

        self.assertIn('version', resp[0])

    @responses.activate
    def test_post_securizer(self):
        self.app.config['SECURIZER'] = True

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))
        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1:.*'),
                               callback=partial(requests_callback_client, self.client))

        data = dict(name='action', version=1, action_type='NATIVE', code='None')
        resp = post(Server.get_current(), 'api_1_0.actiontemplatelist', json=data,
                    auth=self.auth)

        self.assertIn('action_template_id', resp[0])

    @responses.activate
    def test_get_internal_error_server(self):
        self.app.config['SECURIZER'] = True

        responses.add(responses.GET, re.compile('https?://127\.0\.0\.1.*'), status=500,
                      body='<html>Iternal error server</html>')

        data, status = get(Server.get_current(), healthcheck_view, auth=self.auth)

        self.assertEqual(500, status)
        self.assertEqual('<html>Iternal error server</html>', data)

    @responses.activate
    def test_post_securizer(self):
        self.app.config['SECURIZER'] = True

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1.*'),
                               callback=partial(requests_callback_client, self.client))

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json, auth=self.auth)

        self.assertIn('action_template_id', data)

    @responses.activate
    def test_post_no_content_in_response(self):
        self.app.config['SECURIZER'] = True

        def callback_post_client(request):
            return 200, dict(content_type='text/html'), ''

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json, auth=self.auth)

        self.assertEqual(200, status)
        self.assertEqual('', data)

    @responses.activate
    def test_post_no_data_content_type(self):
        self.app.config['SECURIZER'] = True

        def callback_post_client(request):
            self.assertEqual('application/json', request.headers.get('content-type'))
            return 200, dict(content_type='text/html'), ''

        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client)

        data, status = post(Server.get_current(), 'api_1_0.actiontemplatelist', auth=self.auth)

    @responses.activate
    def test_post_connection_error(self):
        self.app.config['SECURIZER'] = True

        responses.add(responses.POST, re.compile('https?://127\.0\.0\.1.*'), body=ConnectionError())

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json, auth=self.auth)

        self.assertEqual(None, status)
        self.assertIsInstance(data, ConnectionError)

    @aioresponses()
    def test_async_get_internal_error_server(self, m):
        self.app.config['SECURIZER'] = True

        m.get(re.compile('https?://127\.0\.0\.1.*'), status=500, body='<html>Iternal error server</html>')

        data, status = run(
            async_get(Server.get_current(), healthcheck_view, auth=self.auth))

        self.assertEqual(500, status)
        self.assertEqual('<html>Iternal error server</html>', data)

    @aioresponses()
    def test_async_post_securizer(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.post(url.path, json=kwargs['json'], headers=self.headers)

            return CallbackResult('POST', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertIn('action_template_id', data)

    @aioresponses()
    def test_async_post_no_content_in_response(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            return CallbackResult('POST', status=200, body='', content_type='text/html')

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertEqual(200, status)
        self.assertEqual('', data)

    @aioresponses()
    def test_async_post_no_data_content_type(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            self.assertEqual('application/json', kwargs.get('headers').get('content-type'))
            return CallbackResult('POST', status=200, body='', content_type='text/html')

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', auth=self.auth))

    @aioresponses()
    def test_async_post_connection_error(self, m):
        self.app.config['SECURIZER'] = True

        m.post(re.compile('https?://127\.0\.0\.1.*'), exception=aiohttp.ClientConnectionError())

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertEqual(None, status)
        self.assertIsInstance(data, aiohttp.ClientConnectionError)

    @aioresponses()
    def test_async_get_error(self, m):
        def callback_get_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=500, body="some error data", content_type='text/html',
                                  headers=r.headers)

        m.get(re.compile('https?://127\.0\.0\.1.*'), callback=callback_get_client, repeat=True)

        data, status = run(async_get(Server.get_current(),
                                     'api_1_0.actiontemplateresource',
                                     view_data=dict(
                                         action_template_id=self.at_json['id']),
                                     auth=self.auth
                                     ))

        self.assertEqual("some error data", data)

    @aioresponses()
    def test_async_get_json_error(self, m):
        def callback_get_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=500, body='{"error":"this is an error message"}',
                                  content_type='application/json',
                                  headers=r.headers)

        m.get(re.compile('https?://127\.0\.0\.1.*'), callback=callback_get_client, repeat=True)

        data, status = run(async_get(Server.get_current(),
                                     'api_1_0.actiontemplateresource',
                                     view_data=dict(
                                         action_template_id=self.at_json['id']),
                                     auth=self.auth
                                     ))

        self.assertDictEqual({"error": "this is an error message"}, data)

    @aioresponses()
    def test_async_get(self, m):
        def callback_get_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.get(re.compile('https?://127\.0\.0\.1.*'), callback=callback_get_client, repeat=True)

        data, status = run(async_get(Server.get_current(),
                                     'api_1_0.actiontemplateresource',
                                     view_data=dict(
                                         action_template_id=self.at_json['id']),
                                     auth=self.auth
                                     ))

        self.assertDictEqual(self.at_json, data)

    @aioresponses()
    def test_async_post(self, m):
        def callback_post_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.post(url.path, json=kwargs['json'], headers=self.headers)

            return CallbackResult('POST', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertIn('action_template_id', data)

    @aioresponses()
    def test_async_get_securizer_error(self, m):
        def callback_get_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=500, body="some error data", content_type='text/html',
                                  headers=r.headers)

        m.get(re.compile('https?://127\.0\.0\.1.*'), callback=callback_get_client, repeat=True)

        data, status = run(async_get(Server.get_current(),
                                     'api_1_0.actiontemplateresource',
                                     view_data=dict(
                                         action_template_id=self.at_json['id']),
                                     auth=self.auth
                                     ))

        self.assertEqual("some error data", data)

    @aioresponses()
    def test_async_get_securizer(self, m):
        self.app.config['SECURIZER'] = True

        def callback_get_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.get(re.compile('https?://127\.0\.0\.1.*'), callback=callback_get_client, repeat=True)

        data, status = run(
            async_get(Server.get_current(), 'api_1_0.actiontemplateresource',
                      view_data=dict(action_template_id=self.at_json['id']), auth=self.auth))

        self.assertIn('version', data)

    @aioresponses()
    def test_async_get_internal_error_server(self, m):
        self.app.config['SECURIZER'] = True

        m.get(re.compile('https?://127\.0\.0\.1.*'), status=500, body='<html>Iternal error server</html>')

        data, status = run(
            async_get(Server.get_current(), healthcheck_view, auth=self.auth))

        self.assertEqual(500, status)
        self.assertEqual('<html>Iternal error server</html>', data)

    @aioresponses()
    def test_async_post_securizer(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client.post(url.path, json=kwargs['json'], headers=self.headers)

            return CallbackResult('POST', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertIn('action_template_id', data)

    @aioresponses()
    def test_async_post_no_content_in_response(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            return CallbackResult('POST', status=200, body='', content_type='text/html')

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertEqual(200, status)
        self.assertEqual('', data)

    @aioresponses()
    def test_async_post_no_data_content_type(self, m):
        self.app.config['SECURIZER'] = True

        def callback_post_client(url, **kwargs):
            self.assertEqual('application/json', kwargs.get('headers').get('content-type'))
            return CallbackResult('POST', status=200, body='', content_type='text/html')

        m.post(re.compile('https?://127\.0\.0\.1.*'), callback=callback_post_client, repeat=True)

        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', auth=self.auth))

    @aioresponses()
    def test_async_post_connection_error(self, m):
        self.app.config['SECURIZER'] = True

        m.post(re.compile('https?://127\.0\.0\.1.*'), exception=aiohttp.ClientConnectionError())

        at_json = dict(name='action', version=1, action_type='NATIVE', code='None')
        data, status = run(
            async_post(Server.get_current(), 'api_1_0.actiontemplatelist', json=at_json,
                       auth=self.auth))

        self.assertEqual(None, status)
        self.assertIsInstance(data, aiohttp.ClientConnectionError)
