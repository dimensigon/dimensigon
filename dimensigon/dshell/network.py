import configparser
import logging
import os
import re
import urllib

import requests
from prompt_toolkit import prompt

from dimensigon import defaults
from dimensigon.dshell import environ as env
from dimensigon.dshell.view_path_mapping import view_path_map
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.utils.helpers import is_iterable_not_string
from dimensigon.web.network import Response

logger = logging.getLogger('dshell.network')


def exists_refresh_token():
    return bool(env._refresh_token)


def bootstrap_auth(username=None, password=None, refresh_token=None):
    if username:
        env._username = username
    if refresh_token:
        env._refresh_token = refresh_token

    if not exists_refresh_token():
        login(username=username, password=password)
    else:
        try:
            refresh_username = refresh_access_token()
        except Exception:
            raise
        else:
            if refresh_username:
                if env._username is None:
                    env._username = refresh_username
                elif env._username != refresh_username:
                    raise ValueError(f"user '{env._username}' does not correspond with the user from the token")


def login(username=None, password=None):
    if not username:
        if not env._username:
            try:
                username = prompt("Username: ")
            except KeyboardInterrupt:
                return
        else:
            username = env._username
    if not password:
        try:
            password = prompt("Password: ", is_password=True)
        except KeyboardInterrupt:
            return

    resp = requests.post(generate_url('root.login', {}), json={'username': username, 'password': password},
                         verify=False)
    resp.raise_for_status()

    env._username = username
    env._access_token = resp.json()['access_token']
    env._refresh_token = resp.json()['refresh_token']

    file = os.path.expanduser(env.get('CONFIG_FILE', None))
    if file and os.path.exists(file):
        config = configparser.ConfigParser()
        config.read(file)
        if config.has_section('AUTH') and config.has_section('REMOTE'):
            if config['AUTH'].get('username') == env._username:
                from dimensigon.dshell.bootstrap import save_config_file
                del config
                save_config_file(token=env._refresh_token)


def refresh_access_token(login_=True):
    url = f"{env.get('SCHEME')}://{env.get('SERVER')}:{env.get('PORT')}/refresh"

    if env._refresh_token is None:
        raise ValueError('empty refresh token. Login first')
    auth = HTTPBearerAuth(env._refresh_token)
    resp = requests.post(url, auth=auth, verify=False, timeout=10)
    if resp.status_code in (401, 422) and login_:
        login()
    else:
        resp.raise_for_status()
        env._access_token = resp.json().get('access_token', None)
        return resp.json().get('username', None)


def request(method, url, session=None, token_refreshed=False, login=True, **kwargs) -> Response:
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

    if 'auth' not in kwargs:
        if env._access_token is None:
            try:
                refresh_access_token(login_=login)
            except requests.exceptions.ConnectionError as e:
                return Response(exception=ConnectionError(f"Unable to contact with {env.get('SCHEME')}://"
                                                          f"{env.get('SERVER')}:{env.get('PORT')}/refresh"),
                                url=url)
            except Exception as e:
                return Response(exception=e, url=url)
            else:
                if env._access_token is None:
                    return Response(exception=ValueError("No authentication set"), url=url)
        kwargs['auth'] = HTTPBearerAuth(env._access_token)

    if 'headers' not in kwargs:
        kwargs['headers'] = {}
    kwargs['headers'].update({'D-Securizer': 'plain'})

    kwargs['verify'] = env.get('SSL_VERIFY')

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
    except requests.ConnectionError as e:
        exception = ConnectionError(f"Unable to contact to {url}")
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
                    refresh_access_token()
                except requests.exceptions.ConnectionError as e:
                    return Response(exception=ConnectionError(f"Unable to contact with {env.get('SCHEME')}://"
                                                              f"{env.get('SERVER')}:{env.get('PORT')}/refresh"),
                                    url=url)
                kwargs['auth'] = HTTPBearerAuth(env._access_token)
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
    replaced_path = path
    match = re.search(r'\<((\w+:)?([\w_]+))\>', path)
    while match:
        text = match.groups()[2]
        assert text in args
        value = args.pop(text)
        if not value:
            raise ValueError(f"No value specified for '{text}' in URL {path}")
        replaced_path = "{}{}{}".format(replaced_path[:match.start()], value, replaced_path[match.end():])
        match = re.search(r'\<((\w+:)?([\w_]+))\>', replaced_path)

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


def generate_url(view, view_data, ip=None, port=defaults.DEFAULT_PORT, scheme='https'):
    try:
        path = view_path_map[view]
    except KeyError:
        raise RuntimeError(f"'{view}' not set in metadata")
    path = _replace_path_args(path, view_data or {})
    if (env.get('SERVER', ip) or ip) is None:
        raise ValueError('No SERVER specified.')
    return f"{env.get('SCHEME', scheme) or scheme}://" \
           f"{env.get('SERVER', ip) or ip}:" \
           f"{env.get('PORT', port) or port}" \
           f"{path}"


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
