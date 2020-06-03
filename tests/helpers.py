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

import requests
from aioresponses import aioresponses, CallbackResult
from flask.testing import FlaskClient
from flask_jwt_extended import create_access_token


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
            r = func(url.path, headers=kwargs['headers'], json=kwargs['json'])
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