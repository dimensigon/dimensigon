import asyncio
import concurrent
import logging
import typing as t

import aiohttp
import requests
import rsa
from aiohttp import ContentTypeError
from flask import current_app as __ca, current_app, url_for
from requests.auth import AuthBase
from requests.exceptions import Timeout

from dm import defaults
from dm.domain.entities import Server, Dimension, Gate
from dm.network.exceptions import NotValidMessage
from dm.network.gateway import pack_msg as _pack_msg, unpack_msg as _unpack_msg
from dm.utils.typos import Kwargs
from dm.web import errors

requests.packages.urllib3.disable_warnings()

logger = logging.getLogger('dm.network')


class Response:

    def __init__(self, msg: t.Union[str, t.Dict[str, t.Any]] = None, code: int = None, exception: Exception = None,
                 server=None,
                 url=None):
        self.code = code
        self.msg = msg
        self.exception = exception
        self.server = server
        self.url = url

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


def ping(dest: t.Union[Server, Gate], source: Server, retries=3, timeout=3, verify=False):
    tries = 0
    cost = None
    elapsed = None
    exc = None

    if isinstance(dest, Gate):
        server = dest.server
        schema = current_app.config['PREFERRED_URL_SCHEME'] or 'https'
        url = f"{schema}://{dest}/{url_for('root.ping', _external=False)}"
    else:
        server = dest
        try:
            url = dest.url('root.ping')
        except:
            logger.exception(f"exception while getting url to {dest}")
            return None, None
    while tries < retries:
        try:
            tries += 1
            resp = requests.post(url,
                                 json={'source': str(source.id)},
                                 headers={'D-Destination': str(server.id)},
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
            cost = resp.json().get('hops', 0)
            elapsed = resp.elapsed
            tries = retries
    if exc:
        if isinstance(exc, requests.exceptions.ReadTimeout):
            logger.warning(f'Timeout reached while trying to access to {url}')
        elif isinstance(exc, requests.exceptions.ConnectionError):
            logger.debug(f'Unable to connect with {url}')
    return cost, elapsed


class HTTPBearerAuth(AuthBase):
    def __init__(self, token):
        self.token = token

    def __eq__(self, other):
        return self.token == getattr(other, 'token', None)

    def __ne__(self, other):
        return not self == other

    def __call__(self, r):
        if hasattr(r, 'headers'):
            r.headers.update(self.header)
        else:
            r['headers'].update(self.header)
            r.pop('auth', None)
        return r

    @property
    def header(self):
        return {'Authorization': str(self)}

    def __str__(self):
        return 'Bearer ' + self.token


def _prepare_url(server: Server, view_or_url: str, view_data=None):
    if view_or_url.startswith('\\'):
        url = server.url() + 'view_or_url'
    else:
        view_data = view_data or {}
        url = server.url(view_or_url, **view_data)
    return url


def _prepare_headers(server, headers=None):
    headers = headers or {}
    headers.update({'D-Destination': str(server.id)})
    headers.update({'D-Source': str(Server.get_current().id)})
    return headers


def prepare_request(server, view_or_url, view_data, kwargs):
    params = kwargs.pop('params', {}) or {}

    url = _prepare_url(server, view_or_url, dict(**view_data, **params))

    kwargs['headers'] = _prepare_headers(server, kwargs.get('headers'))

    if 'auth' in kwargs and kwargs['auth'] is not None:
        kwargs['auth'](kwargs)

    if 'json' in kwargs and kwargs['json']:
        kwargs['json'] = pack_msg(kwargs['json'])

    return url


def request(method, server, view_or_url, view_data=None, session=None, **kwargs) -> Response:
    exception = None
    content = None
    status = None
    json_data = None

    if not session:
        _session = requests.session()

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

    kwargs['verify'] = current_app.config['SSL_VERIFY']

    try:
        resp: requests.Response = func(url, **kwargs)
    except (Timeout, ) as e:
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

    if exception is None:
        status = resp.status_code
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

    return Response(msg=content, code=status, exception=exception, server=server, url=url)


def get(server: Server, view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
        params: Kwargs = None, **kwargs) -> Response:
    """Sends a GET request."""
    return request('get', server, view_or_url, view_data=view_data, session=session, params=params, **kwargs)


def options(server: Server, view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
            **kwargs) -> Response:
    r"""Sends an OPTIONS request."""

    return request('options', server, view_or_url, view_data=view_data, session=session, **kwargs)


def head(server: Server, view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
         **kwargs) -> Response:
    r"""Sends a HEAD request."""
    return request('head', server, view_or_url, view_data=view_data, session=session, **kwargs)


def post(server: Server, view_or_url: str, view_data: Kwargs = None, session: requests.Session = None, data=None,
         json=None, **kwargs) -> Response:
    r"""Sends a POST request."""
    return request('post', server, view_or_url, view_data=view_data, session=session, json=json or {}, **kwargs)


def put(server: Server, view_or_url: str, view_data: Kwargs = None, session: requests.Session = None, data=None,
        **kwargs) -> Response:
    r"""Sends a PUT request."""
    return request('put', server, view_or_url, view_data=view_data, session=session, **kwargs)


def patch(server: Server, view_or_url: str, view_data: Kwargs = None, session: requests.Session = None, data=None,
          **kwargs) -> Response:
    r"""Sends a PATCH request."""
    return request('patch', server, view_or_url, view_data=view_data, session=session, **kwargs)


def delete(server: Server, view_or_url: str, view_data: Kwargs = None, session: requests.Session = None,
           **kwargs) -> Response:
    r"""Sends a DELETE request."""
    return request('delete', server, view_or_url, view_data=view_data, session=session, **kwargs)


async def async_request(method, server, view_or_url, view_data=None, session=None, **kwargs) -> Response:
    exception = None
    content = None
    json_data = None
    status = None
    headers = None

    if not session:
        _session = aiohttp.ClientSession()
    else:
        _session = session

    raise_on_error = kwargs.pop('raise_on_error', False)

    try:
        url = prepare_request(server, view_or_url, view_data or {}, kwargs)
    except Exception as e:
        if raise_on_error:
            raise
        return Response(exception=e, server=server)

    kwargs['ssl'] = current_app.config['SSL_VERIFY']

    if 'timeout' in kwargs and isinstance(kwargs['timeout'], (int, float)):
        kwargs['timeout'] = aiohttp.ClientTimeout(total=kwargs['timeout'])

    func = getattr(_session, method)

    try:
        async with func(url, **kwargs) as resp:
            status = resp.status
            try:
                json_data = await resp.json()
            except (ContentTypeError, ValueError):
                content = await resp.text()
    except (concurrent.futures.TimeoutError, asyncio.TimeoutError) as e:
        exception = TimeoutError(f"Socket timeout reached while trying to connect to {url} "
                  f"for {kwargs.get('timeout').total or _session._timeout.total} seconds")
    except Exception as e:
        exception = e
    finally:
        if not session:
            await _session.close()

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

    return Response(msg=content, code=status, exception=exception, server=server, url=url)


async def async_get(server: Server, view_or_url: str, view_data: Kwargs = None, session: aiohttp.ClientSession = None,
                    params: Kwargs = None, **kwargs) -> Response:
    """Sends a GET request."""
    return await async_request('get', server, view_or_url, view_data=view_data, session=session, params=params, **kwargs)


async def async_options(server: Server, view_or_url: str, view_data: Kwargs = None,
                        session: aiohttp.ClientSession = None,
                        **kwargs) -> Response:
    r"""Sends an OPTIONS request."""

    return await async_request('options', server, view_or_url, view_data=view_data, session=session, **kwargs)


async def async_head(server: Server, view_or_url: str, view_data: Kwargs = None, session: aiohttp.ClientSession = None,
                     **kwargs) -> Response:
    r"""Sends a HEAD request."""
    return await async_request('head', server, view_or_url, view_data=view_data, session=session, **kwargs)


async def async_post(server: Server, view_or_url: str, view_data: Kwargs = None, session: aiohttp.ClientSession = None,
                     json=None, **kwargs) -> Response:
    r"""Sends a POST request."""
    return await async_request('post', server, view_or_url, view_data=view_data, session=session, json=json,
                               **kwargs)


async def async_put(server: Server, view_or_url: str, view_data: Kwargs = None, session: aiohttp.ClientSession = None,
                    json=None, **kwargs) -> Response:
    r"""Sends a PUT request."""
    return await async_request('put', server, view_or_url, view_data=view_data, session=session, json=json, **kwargs)


async def async_patch(server: Server, view_or_url: str, view_data: Kwargs = None, session: aiohttp.ClientSession = None,
                      json=None, **kwargs) -> Response:
    r"""Sends a PATCH request."""
    return await async_request('patch', server, view_or_url, view_data=view_data, session=session, json=json, **kwargs)


async def async_delete(server: Server, view_or_url: str, view_data: Kwargs = None,
                       session: aiohttp.ClientSession = None,
                       **kwargs) -> Response:
    r"""Sends a DELETE request."""
    return await async_request('delete', server, view_or_url, view_data=view_data, session=session, **kwargs)
