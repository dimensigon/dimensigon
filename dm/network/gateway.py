import base64
import json
import pickle
import typing as t

import aiohttp
import flask
import requests
import rsa
from flask import current_app

from dm.domain.entities import Server
from dm.utils.helpers import generate_url, encrypt, decrypt
from dm.web import PROTOCOL

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


def pack_msg(data,
             destination: t.Union[Server, str] = None,
             source: t.Union[Server, str] = None,
             pub_key: rsa.PublicKey = None,
             priv_key: rsa.PrivateKey = None,
             cipher_key: bytes = None,
             symmetric_key: bytes = None) -> t.Dict[str, t.Any]:
    """
    formats data in a well known encrypted structure. See Return.

    Parameters
    ----------
    destination
    source
    pub_key:
        public key object rsa.PublicKey. Used for encrypting the symmetric key
    priv_key:
        private key object rsa.PrivateKey. Private key must be provided for signing structure and when cipher_key
        provided. If not, no signature will be added.
    cipher_key:
        encrypted symmetric key used for data encryption. If set, symmetric_key must be None
    symmetric_key:
        symmetric key to be used for data encryption. If None, randomly generated from cryptography.fernet.Fernet.generate_key()
    data:
        data to encrypt. Data is pickled and then encoded

    Returns
    -------
    returns a dict with the following structure:
        { "destination": "UUID",
          "source": "UUID",
          "data": "encrypted_data",
          "key": "encrypted symmetric key",
          "signature": "current data signature"
        }

    if no priv_key specified it does not encrypt the data. 'key' and 'signature' will not append to the structure.
    if symmetric_key or cipher_key given, 'key' will not append to the structure
    """
    pickled = False
    try:
        dumped_data = json.dumps(data).encode('utf-8')
    except TypeError:
        pickled = True
        dumped_data = pickle.dumps(data)
    if cipher_key:
        if not priv_key:
            raise ValueError('priv_key must be provided to decrypt cipher_key')
        else:
            symmetric_key = rsa.decrypt(cipher_key, priv_key=priv_key)

    if pub_key or symmetric_key:
        data, new_symmetric_key = encrypt(dumped_data if isinstance(dumped_data, bytes) else dumped_data.encode('utf-8'),
                                          symmetric_key=symmetric_key)
    else:
        data, new_symmetric_key = dumped_data, None

    msg = dict(data=base64.b64encode(data).decode('ascii'))

    if destination:
        msg.update(destination=str(destination.id) if isinstance(destination, Server) else destination)
    if source:
        msg.update(source=str(source.id) if isinstance(source, Server) else source)
    if pub_key and new_symmetric_key:
        msg.update(key=base64.b64encode(rsa.encrypt(new_symmetric_key, pub_key)).decode('ascii'))
    if priv_key:
        signature = rsa.sign(json.dumps(msg).encode('ascii'), priv_key, 'SHA-512')
        msg.update(signature=base64.b64encode(signature).decode('ascii'))
    return msg


def unpack_msg(msg, pub_key: rsa.PublicKey = None, priv_key: rsa.PrivateKey = None, symmetric_key=None,
               cipher_key=None):
    """
    Unpacks msg. If signature in msg, pub_key must be provided to validate it.  Pub_key must be provided to decrypt
    cipher_key if provided.

    Parameters
    ----------
    msg:
        message to be unpacked
    pub_key:
        public key which will be used for signature validation
    priv_key:
        pivate key used for decrypt the cipher_key
    cipher_key:
        encrypted symmetric key used for data encryption. When None checks in the msg if 'key' specified. If Not, then
        symmetric_key may be used.
    symmetric_key:
        symmetric key to be used for data encryption. If None, cipher_key will be used

    Returns
    -------

    """
    if 'signature' in msg:
        if not pub_key:
            raise ValueError('No public key specified')
        signature = base64.b64decode(msg.pop('signature').encode('ascii'))
        rsa.verify(json.dumps(msg).encode(), signature, pub_key)

    cipher_key = base64.b64decode(msg.pop('key', '').encode('ascii')) or cipher_key
    if cipher_key:
        if not priv_key:
            raise ValueError('No private key specified')
        else:
            symmetric_key = rsa.decrypt(cipher_key, priv_key)

    data = msg.pop('data')

    if symmetric_key:
        data = decrypt(base64.b64decode(data.encode('ascii')), symmetric_key)
    else:
        data = base64.b64decode(data.encode('ascii'))

    try:
        data = pickle.loads(data)
    except pickle.PickleError:
        data = json.loads(data)

    msg.update(data=data)
    return msg.get('data')


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
    json = pack_msg(destination, source, pub_key, priv_key, data=data)
    r = requests.post(url, json=json)
    # TODO Handle errors codes in HTTP to convert to understandable errors in Domain Application
    if raise_for_status:
        r.raise_for_status()
    try:
        response = r.json()
    except ValueError:
        response = r.text()
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
    json = pack_msg(destination, source, pub_key, priv_key, data=data)
    async with aiohttp.ClientSession() as s:
        r = await s.post(url, json=json)
        # TODO Handle errors codes in HTTP to convert to understandable errors in Domain Application
        if raise_for_status:
            r.raise_for_status()
        return await r.text(), r.status


def proxy_request(request: flask.Request, destination: Server) -> requests.Response:
    url = generate_url(destination=destination, uri=request.full_path, protocol=PROTOCOL)
    json = request.get_json()

    if request.path == '/ping':
        json['hops'] = json.get('hops', 0) + 1

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

    return requests.request(request.method, url, stream=True, **kwargs)


def ping(server: Server, retries=3, timeout=3):
    tries = 0
    cost = None
    elapsed = None
    while tries < retries:
        try:
            tries += 1
            resp = requests.post(
                server.gateway.url('root.ping') if server.gateway else server.url('root.ping'),
                json={'source': str(current_app.server.id), 'destination': str(server.id)},
                verify=False,
                timeout=timeout)
        except (TimeoutError, requests.exceptions.ConnectionError):
            # unable to reach actual server through current gateway, we will get the new gateway
            resp = None
        if resp is not None and resp.status_code == 200:
            cost = resp.json().get('hops', 0)
            elapsed = resp.elapsed
    return cost, elapsed
