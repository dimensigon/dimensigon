import asyncio
import concurrent
import logging
import time
import typing as t

import aiohttp
import requests
import rsa
from aiohttp import ContentTypeError, ClientConnectorError
from flask import current_app as __ca, current_app, url_for, json
from requests.exceptions import Timeout

from dimensigon import defaults
from dimensigon.domain.entities import Server, Dimension, Gate
from dimensigon.network.encryptation import pack_msg as _pack_msg, unpack_msg as _unpack_msg
from dimensigon.network.exceptions import NotValidMessage
from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import Kwargs, tJSON, Id
from dimensigon.web import errors, db
from dimensigon.web.helpers import generate_http_auth

requests.packages.urllib3.disable_warnings()

logger = logging.getLogger('dm.network')

log_requests_with_elapsed = 3


class Response:

    def __init__(self, msg: tJSON = None, code: int = None, exception: Exception = None,
                 server=None,
                 url=None, headers=None):
        self.code = code
        self.msg = msg
        self.exception = exception
        self.server = server
        self.url = url
        self.headers = headers

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
               and self.code == other.code \
               and self.msg == other.msg \
               and self.server == other.server \
               and self.url == other.url \
               and ((self.exception.__class__ == other.exception.__class__ and
                     self.exception.args == other.exception.args) if self.exception else True)

    # backward compatibility <= v0.1-b10
    def __iter__(self):
        yield self.exception or self.msg
        yield self.code

    # backward compatibility <= v0.1-b10
    def __getitem__(self, item):
        if item == 0:
            return self.exception or self.msg
        elif item == 1:
            return self.code
        raise KeyError(item)

    def __repr__(self):
        return f"Response(server={self.server}, url={self.url}, code={self.code})"

    def __str__(self):
        if self.exception:
            return f"{self.exception.__class__.__name__}: {self.exception}"
        if isinstance(self.msg, dict):
            return f"{self.code}, {json.dumps(self.msg, indent=2)}"
        else:
            return f"{self.code}, {self.msg}"

    def to_dict(self):
        dump = dict()
        if self.code:
            dump.update(code=self.code, response=self.msg)
            if self.url:
                dump.update(url=self.url)
            if self.server:
                dump.update(server=dict(id=str(self.server.id), name=self.server.name))
        else:
            dump.update(exception=str(self.exception) if str(self.exception) else self.exception.__class__.__name__)
        return dump

    def raise_on_error(self):
        if self.exception:
            raise self.exception

    def raise_for_status(self):
        if self.code < 200 or 299 < self.code:
            raise errors.HTTPError(self)

    def raise_if_not_ok(self):
        self.raise_on_error()
        self.raise_for_status()

    @property
    def ok(self):
        return not bool(self.exception) and bool(self.code) and 200 <= self.code <= 299


def pack_msg(data, *args, **kwargs):
    if not __ca.config['SECURIZER']:
        return data
    else:
        # if not ('symmetric_key' in kwargs or 'cipher_key' in kwargs):
        #     try:
        #         kwargs['cipher_key'] = session.get('cipher_key')
        #     except RuntimeError:
        #         pass
        # if generate_key:
        #     kwargs.pop('symmetric_key', None)
        #     kwargs.pop('cipher_key', None)
        dim = None
        if dim is None:
            dim = Dimension.get_current()
            if dim is None:
                raise ValueError('No dimension found but SECURIZER set')
        return _pack_msg(data, *args, source=Server.get_current(),
                         pub_key=dim.public,
                         priv_key=dim.private,
                         **kwargs)


def pack_msg2(data, *args, **kwargs):
    if not __ca.config['SECURIZER']:
        return data
    else:
        return _pack_msg(data, *args, **kwargs)


def unpack_msg(data, *args, **kwargs):
    if not __ca.config['SECURIZER']:
        return data
    else:
        # if 'key' in data:
        #     cipher_key = base64.b64decode(data.get('key'))
        # else:
        #     try:
        #         cipher_key = session.get('cipher_key', None)
        #     except RuntimeError:
        #         cipher_key = None
        # try:
        #     session['cipher_key'] = cipher_key
        # except RuntimeError:
        #     pass
        if not 'error' in data:
            dim = None
            if dim is None:
                dim = Dimension.get_current()
                if dim is None:
                    raise ValueError('No dimension found but SECURIZER set')
            return _unpack_msg(data, *args, pub_key=dim.public,
                               priv_key=dim.private, **kwargs)
        else:
            return data


def unpack_msg_no_ctx(data, securizer: bool, public_key: rsa.PublicKey, private_key: rsa.PrivateKey, *args, **kwargs):
    if not securizer:
        return data
    else:
        if not 'error' in data:
            return _unpack_msg(data, *args, pub_key=public_key,
                               priv_key=private_key, **kwargs)
        else:
            return data


def unpack_msg2(data, *args, **kwargs):
    if not __ca.config['SECURIZER']:
        return data
    else:
        if not 'error' in data:
            return _unpack_msg(data, *args, **kwargs)
        else:
            return data


def ping(dest: t.Union[Server, Gate], retries=3, timeout=30, verify=False, session=None):
    server = Server.get_current(session=session)
    return _ping(dest=dest, source=server, retries=retries, timeout=timeout, verify=verify)


def _ping(dest: t.Union[Server, Gate], source: Server, retries=None, timeout=None, verify=False):
    tries = 0
    cost = None
    elapsed = None
    exc = None

    if isinstance(dest, Gate):
        server = dest.server
        try:
            schema = current_app.config['PREFERRED_URL_SCHEME'] or 'https'
        except:
            schema = 'https'
        url = f"{schema}://{dest}/{url_for('root.ping', _external=False)}"
    else:
        server = dest
        try:
            url = dest.url('root.ping')
        except:
            return None, None
    while tries < retries:
        try:
            tries += 1
            resp = requests.post(url,
                                 json={'start_time': get_now().strftime(defaults.DATETIME_FORMAT)},
                                 headers={'D-Source': str(source.id), 'D-Destination': str(server.id)},
                                 verify=verify,
                                 timeout=timeout)
        except requests.exceptions.ReadTimeout as e:
            resp = None
            exc = e
        except requests.exceptions.ConnectionError as e:
            # unable to reach actual server through current gateway
            resp = None
            exc = e
        if resp is not None and resp.status_code == 200:
            cost = len(resp.json().get('servers', {}))
            elapsed = resp.elapsed
            tries = retries
    return cost, elapsed


def _prepare_url(server: t.Union[Server, str], view_or_url: str, view_data=None):
    if isinstance(server, Server):
        if view_or_url.startswith('/'):
            url = server.url() + view_or_url
        else:
            view_data = view_data or {}
            url = server.url(view_or_url, **view_data)
    else:
        try:
            scheme = 'http' if current_app.dm and 'keyfile' not in current_app.dm.config.http_conf else 'https'
        except:
            scheme = 'https'
        root_path = f"{scheme}://{server}"
        if view_or_url.startswith('/'):
            url = root_path + view_or_url
        else:
            view_data = view_data or {}
            url = root_path + url_for(view_or_url, **view_data)
    return url


def _prepare_headers(server: t.Union[Server, str], headers=None):
    headers = headers or {}
    if isinstance(server, Server):
        headers.update({'D-Destination': str(server.id)})
    headers.update({'D-Source': str(Server.get_current().id)})
    return headers


def prepare_request(server: t.Union[Server, str], view_or_url, view_data, kwargs):
    params = kwargs.pop('params', {}) or {}

    url = _prepare_url(server, view_or_url, dict(**view_data, **params))

    kwargs['headers'] = _prepare_headers(server, kwargs.get('headers'))

    securizer = kwargs.pop('securizer', True)

    if 'auth' in kwargs and kwargs['auth'] is not None:
        kwargs['auth'](kwargs)
    else:
        generate_http_auth()(kwargs)

    if 'json' in kwargs and kwargs['json'] and securizer:
        kwargs['json'] = pack_msg(kwargs['json'])

    return url


def request(method: str, server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None,
            session=None, **kwargs) -> Response:
    exception = None
    content = None
    status = None
    json_data = None
    headers = None

    if not session:
        _session = requests.session()
    else:
        _session = session

    raise_on_error = kwargs.pop('raise_on_error', False)

    try:
        url = prepare_request(server, view_or_url, view_data or {}, kwargs)
    except Exception as e:
        if raise_on_error:
            raise
        return Response(exception=e, server=server)

    func = getattr(_session, method.lower())

    if 'timeout' not in kwargs:
        kwargs['timeout'] = defaults.TIMEOUT_REQUEST

    kwargs['verify'] = False
    start = time.time()
    try:
        resp: requests.Response = func(url, **kwargs)
    except (Timeout,) as e:
        timeout = kwargs.get('timeout', None)
        if isinstance(timeout, tuple):
            timeout = timeout[0] + timeout[1]
        exception = TimeoutError(f"Socket timeout reached while trying to connect to {url} "
                                 f"for {timeout} seconds")
    except Exception as e:
        exception = e
    finally:
        if not session:
            _session.close()
    elapsed = time.time() - start
    if elapsed > log_requests_with_elapsed:
        logger.debug(f"{method.upper()} {url} elapsed time: {elapsed}")
    if exception is None:
        status = resp.status_code
        headers = resp.headers
        try:
            json_data = resp.json()
        except (ValueError,):
            content = resp.text

        if json_data:
            try:
                content = unpack_msg(json_data)
            except NotValidMessage:
                content = json_data
    else:
        if raise_on_error:
            raise exception

    return Response(msg=content, code=status, exception=exception, server=server, url=url, headers=headers)


def get(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
        params: Kwargs = None, **kwargs) -> Response:
    """Sends a GET request."""
    return request('get', server, view_or_url, view_data=view_data, session=session, params=params, **kwargs)


def options(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
            **kwargs) -> Response:
    r"""Sends an OPTIONS request."""

    return request('options', server, view_or_url, view_data=view_data, session=session, **kwargs)


def head(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
         **kwargs) -> Response:
    r"""Sends a HEAD request."""
    return request('head', server, view_or_url, view_data=view_data, session=session, **kwargs)


def post(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
         json=None, **kwargs) -> Response:
    r"""Sends a POST request."""
    return request('post', server, view_or_url, view_data=view_data, session=session, json=json or {}, **kwargs)


def put(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
        **kwargs) -> Response:
    r"""Sends a PUT request."""
    return request('put', server, view_or_url, view_data=view_data, session=session, **kwargs)


def patch(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
          **kwargs) -> Response:
    r"""Sends a PATCH request."""
    return request('patch', server, view_or_url, view_data=view_data, session=session, **kwargs)


def delete(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
           **kwargs) -> Response:
    r"""Sends a DELETE request."""
    return request('delete', server, view_or_url, view_data=view_data, session=session, **kwargs)


async def async_request(method: str, server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None,
                        session=None, **kwargs) -> Response:
    exception = None
    content = None
    json_data = None
    status = None
    headers = None

    if session is None:
        _session = aiohttp.ClientSession()
    else:
        _session = session

    try:
        raise_on_error = kwargs.pop('raise_on_error', False)

        try:
            url = prepare_request(server, view_or_url, view_data or {}, kwargs)
        except Exception as e:
            if raise_on_error:
                raise
            return Response(exception=e, server=server)

        kwargs['ssl'] = False

        if 'timeout' in kwargs and isinstance(kwargs['timeout'], (int, float)):
            kwargs['timeout'] = aiohttp.ClientTimeout(total=kwargs['timeout'])

        func = getattr(_session, method)

        # start = time.time()
        try:
            async with func(url, **kwargs) as resp:
                status = resp.status
                headers = resp.headers
                try:
                    json_data = await resp.json()
                except (ContentTypeError, ValueError):
                    content = await resp.text()
        except (concurrent.futures.TimeoutError, asyncio.TimeoutError) as e:
            exception = TimeoutError(f"Socket timeout reached while trying to connect to {url} "
                                     f"for {kwargs.get('timeout').total or _session._timeout.total} seconds")
        except ClientConnectorError as e:
            exception = ConnectionRefusedError(
                f"Cannot connect to host {e.host}:{e.port} ssl:{e.ssl if e.ssl is not None else 'default'}")
        except Exception as e:
            exception = e
    finally:
        if session is None:
            await _session.close()
    # elapsed = time.time() - start
    # if elapsed > log_requests_with_elapsed:
    #     logger.debug(f"async {method.upper()} {url} elapsed time: {elapsed}")
    if json_data:
        try:
            content = unpack_msg(json_data)
        except NotValidMessage:
            content = json_data
    elif exception:
        if raise_on_error:
            raise exception
    else:
        content = await resp.text()

    return Response(msg=content, code=status, exception=exception, server=server, url=url, headers=headers)


async def async_get(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None,
                    session: aiohttp.ClientSession = None,
                    params: Kwargs = None, **kwargs) -> Response:
    """Sends a GET request."""
    return await async_request('get', server, view_or_url, view_data=view_data, session=session, params=params,
                               **kwargs)


async def async_options(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None,
                        session: aiohttp.ClientSession = None,
                        **kwargs) -> Response:
    r"""Sends an OPTIONS request."""

    return await async_request('options', server, view_or_url, view_data=view_data, session=session, **kwargs)


async def async_head(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None,
                     session: aiohttp.ClientSession = None,
                     **kwargs) -> Response:
    r"""Sends a HEAD request."""
    return await async_request('head', server, view_or_url, view_data=view_data, session=session, **kwargs)


async def async_post(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None,
                     session: aiohttp.ClientSession = None,
                     json=None, **kwargs) -> Response:
    r"""Sends a POST request."""
    return await async_request('post', server, view_or_url, view_data=view_data, session=session, json=json,
                               **kwargs)


async def async_put(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None,
                    session: aiohttp.ClientSession = None,
                    json=None, **kwargs) -> Response:
    r"""Sends a PUT request."""
    return await async_request('put', server, view_or_url, view_data=view_data, session=session, json=json, **kwargs)


async def async_patch(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None,
                      session: aiohttp.ClientSession = None,
                      json=None, **kwargs) -> Response:
    r"""Sends a PATCH request."""
    return await async_request('patch', server, view_or_url, view_data=view_data, session=session, json=json, **kwargs)


async def async_delete(server: t.Union[Server, str], view_or_url: str, view_data: Kwargs = None,
                       session: aiohttp.ClientSession = None,
                       **kwargs) -> Response:
    r"""Sends a DELETE request."""
    return await async_request('delete', server, view_or_url, view_data=view_data, session=session, **kwargs)


async def parallel_requests(servers: t.List[t.Union[Server, Id]], method: str, kw_wrapper=None, **kwargs):
    if not servers:
        return []

    if not isinstance(servers[0], Server):
        servers = [Server.query.get(s) for s in servers]
    else:
        servers = [db.session.merge(s) if s not in db.session else s for s in servers]

    if not kwargs.get('session'):
        _session = aiohttp.ClientSession()
        close = True
    else:
        close = False
        _session = kwargs.get('session')
    kwargs['session'] = _session

    try:
        aw = []
        for s in servers:
            if kw_wrapper:
                kw_wrapper(s, kwargs)
            aw.append(async_request(method.lower(), s, **kwargs))

        rs = await asyncio.gather(*aw, return_exceptions=True)
    finally:
        if close:
            await _session.close()

    db.session.close()
    return rs
