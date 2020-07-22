import functools
import re
import sys
import time
import traceback
import typing as t
from contextlib import contextmanager
from http.server import HTTPServer
from io import StringIO
from threading import Thread
from unittest import TestCase, mock
from unittest.mock import Mock

import flask
import requests
from aioresponses import aioresponses, CallbackResult
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask.testing import FlaskClient
from flask_jwt_extended import create_access_token

from dm import defaults
from dm.domain.entities import User, update_datemark
from dm.network.auth import HTTPBearerAuth
from dm.utils.helpers import get_entities, get_distributed_entities
from dm.web import create_app, db, errors


def start_mock_server(port, mock_server_request_handler):
    mock_server = HTTPServer(('localhost', port), mock_server_request_handler)
    mock_server_thread = Thread(target=mock_server.serve_forever)
    mock_server_thread.setDaemon(True)
    mock_server_thread.start()


def set_response_from_mock(mock: Mock, url: str, status: int, json: t.Union[str, t.Mapping[str, t.Any]],
                           headers: t.Mapping[str, str] = None):
    """
    Function to mock a requests.HTTP_METHOD
    Parameters
    ----------
    mock
    url
    status
    json
    headers

    Returns
    -------
    None
    """
    resp = requests.Response()
    resp.url = url
    resp.headers = headers or {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json'}
    resp.status_code = status
    resp._content = str(json).encode()
    mock.return_value = resp


def wait_mock_called(mock: Mock, call_count: int, timeout: int = 10):
    """Waits for a mock to be called at least call_count times. Raise a TimeoutError if timeout reached"""
    start = time.time()
    while time.time() < (timeout + start):
        if mock.call_count >= call_count:
            return
        else:
            time.sleep(0.01)
    raise TimeoutError('Timeout reached while waiting for mock to be called')


@contextmanager
def captured_output() -> t.Tuple[StringIO, StringIO]:
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err




def authorization_header(identity='test'):
    access_token = create_access_token(identity=identity)
    return {"Authorization": f"Bearer {access_token}"}


class TestCaseLockBypass(TestCase):

    def run(self, result=None):
        with mock.patch('dm.use_cases.lock.lock'):
            with mock.patch('dm.use_cases.lock.unlock'):
                super().run(result)


def set_callbacks(target: t.List[t.Tuple[str, FlaskClient]], m: aioresponses = None):
    import responses
    method_list = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

    def requests_callback_client(client, request):
        method_func = getattr(client, request.method.lower())
        try:
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
        except Exception as e:
            return 500, {}, traceback.format_exc()

        return resp.status_code, resp.headers, resp.data

    def callback_client(method, client, url, **kwargs):
        kwargs.pop('allow_redirects')
        # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
        func = getattr(client, method.lower())
        try:
            r = func(url.path, headers=kwargs['headers'], json=kwargs.get('json'))
        except Exception as e:
            return CallbackResult(method.upper(), status=500, body=traceback.format_exc(), headers={})

        return CallbackResult(method.upper(), status=r.status_code, body=r.data, content_type=r.content_type,
                              headers=r.headers)

    for dest_regexp, client in target:

        for method in method_list:
            responses.add_callback(method, re.compile(f'https?://{dest_regexp}.*'),
                                   callback=functools.partial(requests_callback_client, client))
        if m:
            for method in method_list:
                func = getattr(m, method.lower())
                func(re.compile(f'https?://{dest_regexp}.*'),
                     callback=functools.partial(callback_client, method, client), repeat=True)


class ValidateResponseMixin:

    def validate_error_response(self, resp: flask.Response, error: errors.BaseError):
        self.assertEqual(error.status_code, resp.status_code)
        self.assertDictEqual(errors.format_error_content(error), resp.get_json())


class TestDimensigonBase(TestCase, ValidateResponseMixin):

    def setUp(self) -> None:
        self.maxDiff = None
        self.app = create_app('test')
        self.app.config['SECURIZER'] = False
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        User.set_initial()
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()


def generate_dimension_json_data():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=1024,
        backend=default_backend()
    )
    priv_pem = private_key.private_bytes(encoding=serialization.Encoding.PEM,
                                         format=serialization.PrivateFormat.TraditionalOpenSSL,
                                         encryption_algorithm=serialization.NoEncryption())
    pub_pem = private_key.public_key().public_bytes(encoding=serialization.Encoding.PEM,
                                                    format=serialization.PublicFormat.PKCS1)

    return {'id': '0000000d-0000-0000-0000-000000000001', 'name': 'dimension',
            'private': priv_pem.decode('ascii'),
            'public': pub_pem.decode('ascii'),
            'created_at': defaults.INITIAL_DATEMARK.strftime(defaults.DATETIME_FORMAT), 'current': True}


def load_data(catalog: t.Dict[str, t.List[t.Dict]]):
    e = dict(get_entities())
    de = dict(get_distributed_entities())

    for name, dtos in catalog:
        cls = e[name]
        for dto in dtos:
            if 'last_modified_at' in dto and name in de:
                update_datemark(False)
            o = cls.from_json(dto)
            db.session.add(o)
            db.session.commit()
            if 'last_modified_at' in dto and name in de:
                update_datemark(True)
