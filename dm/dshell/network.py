import logging
import os
import re
import urllib

import requests
from prompt_toolkit import prompt

from dm import defaults
from dm.dshell import environ
from dm.dshell.view_path_mapping import view_path_map
from dm.network.auth import HTTPBearerAuth
from dm.utils.helpers import is_iterable_not_string
from dm.web.network import Response

logger = logging.getLogger('dshell.network')

_access_token = None
_refresh_token = os.environ.get('DM_REFRESH_TOKEN')
_username = None


def bootstrap_auth(username=None, password=None, refresh_token=None):
    global _username, _refresh_token

    if username:
        _username = username
    if refresh_token:
        _refresh_token = refresh_token

    if not exists_refresh_token():
        login(username=username, password=password)
    else:
        try:
            refresh_username = refresh_access_token()
        except Exception:
            raise
        else:
            if refresh_username:
                if _username is None:
                    _username = refresh_username
                elif _username != refresh_username:
                    raise ValueError(f"user '{_username}' does not correspond with the user from the token")


def login(username=None, password=None):
    global _access_token, _refresh_token, _username

    if not username:
        if not _username:
            username = prompt("Username: ")
        else:
            username = _username
    if not password:
        password = prompt("Password: ", is_password=True)

    resp = requests.post(generate_url('root.login', {}), json={'username': username, 'password': password},
                         verify=False)
    resp.raise_for_status()

    _username = username
    _access_token = resp.json()['access_token']
    _refresh_token = resp.json()['refresh_token']


def exists_refresh_token():
    return bool(_refresh_token)


def refresh_access_token():
    global _refresh_token, _access_token, _username
    url = f"{environ.get('SCHEME')}://{environ.get('SERVER')}:{environ.get('PORT')}/refresh"

    if _refresh_token is None:
        raise ValueError('empty refresh token. Login first')
    auth = HTTPBearerAuth(_refresh_token)
    resp = requests.post(url, auth=auth, verify=False, timeout=10)
    resp.raise_for_status()
    _access_token = resp.json().get('access_token', None)
    return resp.json().get('username', None)


def request(method, url, session=None, token_refreshed=False, **kwargs) -> Response:
    global _access_token
    exception = None
    content = None
    status = None
    json_data = None
    headers = {}

    if not session:
        _session = requests.session()
    else:
        _session = session

    raise_on_error = kwargs.pop('raise_on_error', False)

    func = getattr(_session, method.lower())

    if _access_token is None:
        try:
            refresh_access_token()
        except requests.exceptions.ConnectionError as e:
            return Response(exception=ValueError(f"Unable to contact with {environ.get('SCHEME')}://"
                                                 f"{environ.get('SERVER')}:{environ.get('PORT')}/"),
                            url=url)
        except Exception as e:
            return Response(exception=e, url=url)
    kwargs['auth'] = HTTPBearerAuth(_access_token)

    if 'headers' not in kwargs:
        kwargs['headers'] = {}
    kwargs['headers'].update({'D-Securizer': 'plain'})

    kwargs['verify'] = False

    logger.debug(f"{method.upper()} {url}\n{kwargs}")

    resp = None
    try:
        resp: requests.Response = func(url, **kwargs)
    except (requests.Timeout,) as e:
        timeout = kwargs.get('timeout', None)
        if isinstance(timeout, tuple):
            timeout = timeout[0] + timeout[1]
        exception = TimeoutError(f"Socket timeout reached while trying to connect to {url} "
                                 f"for {timeout} seconds")
    except Exception as e:
        exception = e
    finally:
        if session is None and not (
                getattr(resp, 'status_code', None) == 401 and resp.json().get('msg') == 'Token has expired'):
            _session.close()
    if exception is None:
        status = resp.status_code
        headers = resp.headers
        if status == 401 and not token_refreshed:
            json_data = resp.json()
            if json_data.get('msg') == 'Token has expired':
                try:
                    _access_token = refresh_access_token()
                except requests.exceptions.ConnectionError as e:
                    return Response(exception=ValueError(f"Unable to contact with {environ.get('SCHEME')}://"
                                                         f"{environ.get('SERVER')}:{environ.get('PORT')}/"),
                                    url=url)
                resp = request(method, url, session=_session, token_refreshed=True, **kwargs)
                if not session:
                    _session.close()
                return resp
        try:
            json_data = resp.json()
        except (ValueError,):
            content = resp.text

        if json_data is not None:
            # try:
            #     content = unpack_msg(json_data)
            # except NotValidMessage:
            #     content = json_data
            content = json_data
    else:
        if raise_on_error:
            raise exception

    return Response(msg=content, code=status, exception=exception, url=url, headers=headers)


def get_parameters_from_path(view):
    path = view_path_map[view]
    match_iterator = re.finditer('\<([\w_]+)\>', path)
    for match in match_iterator:
        yield match.groups()[0]


def _replace_path_args(path, args):
    match_iterator = re.finditer('\<([\w_]+)\>', path)
    replaced_path = path
    for match in match_iterator:
        text = match.groups()[0]
        assert text in args
        replaced_path = replaced_path[:match.start()] + args.pop(text) + replaced_path[match.end():]
    params = []
    if args:
        for k, v in args.items():
            if is_iterable_not_string(v):
                for vv in v:
                    if vv is not None:
                        params.append(f"{k}={urllib.parse.quote_plus(vv)}")
            else:
                if v is not None:
                    params.append(f"{k}={urllib.parse.quote_plus(v)}")
    return replaced_path + '?' + '&'.join(params)


def generate_url(view, view_data):
    path = view_path_map[view]
    path = _replace_path_args(path, view_data or {})
    if environ.get('SERVER') is None:
        raise ValueError('No SERVER specified.')
    return f"{environ.get('SCHEME', 'https') or 'https'}://{environ.get('SERVER')}:{environ.get('PORT', defaults.DEFAULT_PORT) or defaults.DEFAULT_PORT}{path}"


def get(view, view_data=None, **kwargs) -> Response:
    return request('get', generate_url(view, view_data), **kwargs)


def post(view, view_data=None, **kwargs) -> Response:
    return request('post', generate_url(view, view_data), **kwargs)


def put(view, view_data=None, **kwargs) -> Response:
    return request('put', generate_url(view, view_data), **kwargs)


def patch(view, view_data=None, **kwargs) -> Response:
    return request('patch', generate_url(view, view_data), **kwargs)


def delete(view, view_data=None, **kwargs) -> Response:
    return request('delete', generate_url(view, view_data), **kwargs)
