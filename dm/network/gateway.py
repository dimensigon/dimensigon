import typing as t

import aiohttp
import flask
import requests
import rsa
from returns.result import Result

import dm.network.exceptions as e
from dm.domain.entities import Server
from dm.network import TypeMsg
from dm.use_cases.base import Message, MsgExecution
from dm.use_cases.deployment import Command, ProxyCommand
from dm.utils.helpers import encode, generate_url

if t.TYPE_CHECKING:
    from dm.use_cases.mediator import Mediator

PROTOCOL = 'http'

"""
Singleton class that allows communication between servers. create a routes dict like follows:

--------
Create all servers
>>>s1 = Server(name='Server1', ip='127.0.0.1', port=5001, route=[], id=uuid.UUID('12345678-1234-5678-1234-567812345678'))
>>>s2 = Server(name='Server2', ip='127.0.0.1', port=5002, route=[], id=uuid.UUID('22345678-1234-5678-1234-567812345678'))
>>>s3 = Server(name='Server3', ip='127.0.0.1', port=5003, route=[s2], id=uuid.UUID('32345678-1234-5678-1234-567812345678'))
>>>s4 = Server(name='Server4', ip='127.0.0.1', port=5004, route=[s2, s3], id=uuid.UUID('42345678-1234-5678-1234-567812345678'))
Create dict like servers
>>>dict_route = {s1.id: s1, s2.id: s2, s3.id: s3, s4.id: s4}
>>>g = Gateway(routes=dict_route)
"""


def _generate_msg(destination: Server, source: Server, pub_key=None, priv_key=None, data=None):
    data, token = encode(data or {}, key=pub_key)
    json = dict(destination=str(destination.id), source=str(source.id), data=data)
    if priv_key:
        json.update({'token': token})
        hash = rsa.sign(json, priv_key, 'SHA-256')
        json.update({'hash': hash})
    return json


def send_message(destination: Server, source: Server, pub_key=None, priv_key=None, raise_for_status=True, data=None) -> \
        t.Tuple[str, int]:
    """Sends a message to the corresponding server

    Parameters
    ----------
    destination
    source
    pub_key
    priv_key
    raise_for_status
    data

    Returns
    -------
    response t.Tuple[str, int]:
        returns the response from the server in a tuple ('message response', 204) message response from server and
        the corresponding HTTP code.
    """
    url = generate_url(destination, uri='/socket', protocol=PROTOCOL)
    json = _generate_msg(destination, source, pub_key, priv_key, data=data)
    r = requests.post(url, json=json)
    # TODO Handle errors codes in HTTP to convert to understandable errors in Domain Application
    if raise_for_status:
        r.raise_for_status()
    try:
        response = r.json()
    except ValueError:
        response = r.text
    return response, r.status_code


async def async_send_message(destination: Server, source: Server, pub_key=None, priv_key=None, raise_for_status=True,
                             data=None) -> t.Any:
    """Sends a message to the corresponding server

    Parameters
    ----------
    destination:
        server destination
    kwargs:
        kwargs will be sent through network to the destination

    Returns
    -------
    response
        returns the response from the server in a tuple ('message response', 204) message response from server and
        the corresponding HTTP code.
    """
    url = generate_url(destination, uri='/socket', protocol=PROTOCOL)
    json = _generate_msg(destination, source, pub_key, priv_key, data=data)
    async with aiohttp.ClientSession() as s:
        r = await s.post(url, json=json)
        # TODO Handle errors codes in HTTP to convert to understandable errors in Domain Application
        if raise_for_status:
            r.raise_for_status()
        return await r.text(), r.status


def dispatch_message(msg: t.Union[Message, MsgExecution, dict], mediator: 'Mediator') -> t.Any:
    """

    Parameters
    ----------
    msg:
        message to be consumed
    mediator:

    Returns
    -------

    """
    if 'msg_type' in msg:
        if msg.msg_type == TypeMsg.INVOKE_CMD:
            # Validation
            cmd = msg.content.get('command')
            assert isinstance(cmd, (Command, ProxyCommand))
        elif msg.msg_type == (TypeMsg.LOCK, TypeMsg.PREVENT_LOCK, TypeMsg.UNLOCK):
            scope = msg.content.get('scope')
            applicant = msg.content.get('applicant')
            if msg.msg_type == TypeMsg.PREVENT_LOCK:
                action = 'P'
            elif msg.msg_type == TypeMsg.LOCK:
                action = 'L'
            else:
                action = 'U'
            mediator.local_lock_unlock(action, scope, applicant)
        else:
            raise e.UnknownMessageType
    elif 'function' in msg:
        _args = msg.get('args', ())
        _kwargs = msg.get('kwargs', {})
        func = getattr(mediator, msg.get('function'), None)
        if callable(func):
            return func(*_args, **_kwargs)
        else:
            raise e.UnknownFunctionMediator
    elif 'data_log' in msg:
        return mediator.receive_data_log(**msg)


def proxy_request(request: flask.Request, destination: Server) -> requests.Response:
    url = generate_url(destination=destination, uri=request.full_path, protocol=PROTOCOL)
    json = request.get_json()

    kwargs = {
        'json': json,
        'allow_redirects': False
    }

    headers = dict([(key.upper(), value)
                    for key, value in request.headers.items()])

    # Let requests reset the host for us.
    if 'HOST' in headers:
        del headers['HOST']

    kwargs['headers'] = headers

    cookies = request.cookies

    kwargs['cookies'] = cookies

    return requests.request(request.method, url, **kwargs)
