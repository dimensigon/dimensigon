import sys
import time
import typing as t
from contextlib import contextmanager
from http.server import HTTPServer
from io import StringIO
from threading import Thread
from unittest.mock import Mock

import requests
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


#
# def initial_test_data(dimension=None):
#     with session_scope() as s:
#         a1 = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234aaa1'),
#                             name='mkdir',
#                             version=1,
#                             action_type=ActionType.NATIVE,
#                             code='mkdir {dir}',
#                             last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'))
#         a2 = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234aaa2'),
#                             name='rmdir',
#                             version=1,
#                             action_type=ActionType.NATIVE,
#                             code='rmdir {dir}',
#                             last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'))
#         # s.add([a1, a2])
#         o = Orchestration(id='cccccccc-1234-5678-1234-56781234ccc1', name='create folder', version=1,
#                           description='Creates a folder on the specified location',
#                           last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'))
#         s1 = o.add_step(undo=False, stop_on_error=True, action_template=a1, step_expected_output=None,
#                         step_expected_rc=0,
#                         step_parameters={'dir': 'folder'}, step_system_kwargs=None,
#                         last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'),
#                         id=uuid.UUID('eeeeeeee-1234-5678-1234-56781234eee1'))
#         s2 = o.add_step(parents=[s1], undo=False, stop_on_error=True, action_template=a2, step_expected_output=None,
#                         step_expected_rc=0,
#                         step_parameters={'dir': 'folder'}, step_system_kwargs=None,
#                         last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'),
#                         id=uuid.UUID('eeeeeeee-1234-5678-1234-56781234eee2'))
#         s.add(o)
#         srv1 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='localhost.localdomain',
#                       ip='127.0.0.1', port=5000,
#                       last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'), _me=True)
#         srv2 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb2', name='server1.localdomain', ip='127.0.0.1',
#                       port=80, last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'))
#         s.add_all([srv1, srv2])
#
#         c1 = Catalog(entity='ActionTemplate',
#                      last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'))
#         c2 = Catalog(entity='Step', last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'))
#         c3 = Catalog(entity='Orchestration',
#                      last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'))
#         c4 = Catalog(entity='Server', last_modified_at=datetime.strptime('20190101000530100000', '%Y%m%d%H%M%S%f'))
#         s.add_all([c1, c2, c3, c4])
#
#         if dimension:
#             s.add(dimension)
#         s.commit()


def authorization_header(identity='test'):
    access_token = create_access_token(identity=identity)
    return {"Authorization": f"Bearer {access_token}"}
