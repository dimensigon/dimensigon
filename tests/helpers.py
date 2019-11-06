import sys
import time
import typing as t
from io import StringIO
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock

import requests


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