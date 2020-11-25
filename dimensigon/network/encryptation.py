import base64
import copy
import json
import pickle
import typing as t

import rsa

from dimensigon.domain.entities import Server
from dimensigon.utils.helpers import encrypt, decrypt
from .exceptions import NotValidMessage

if t.TYPE_CHECKING:
    pass

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
             symmetric_key: bytes = None,
             add_key=False) -> t.Dict[str, t.Any]:
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
          "enveloped_data": "encrypted_data",
          "key": "encrypted symmetric key",
          "signature": "current data signature"
        }

    if no priv_key specified it does not encrypt the data. 'key' and 'signature' will not append to the structure.
    if symmetric_key or cipher_key given, 'key' will not append to the structure
    """
    try:
        dumped_data: bytes = json.dumps(data).encode('utf-8')
    except TypeError:
        dumped_data: bytes = pickle.dumps(data)

    # get symmetric_key
    if cipher_key:
        if not priv_key:
            raise ValueError('priv_key must be provided to decrypt cipher_key')
        else:
            symmetric_key = rsa.decrypt(cipher_key, priv_key=priv_key)

    # encrypt data
    if pub_key or symmetric_key:
        encrypted_data, new_symmetric_key = encrypt(
            dumped_data,
            symmetric_key=symmetric_key)
    else:
        encrypted_data, new_symmetric_key = dumped_data, None

    msg = dict(enveloped_data=base64.b64encode(encrypted_data).decode('ascii'))

    if destination:
        # warnings.warn("The 'destination' parameter is deprecated, "
        #               "use 'D-Destination header' instead", DeprecationWarning, 2)
        msg.update(destination=str(destination.id) if isinstance(destination, Server) else destination)
    if source:
        msg.update(source=str(source.id) if isinstance(source, Server) else source)
    if pub_key and (new_symmetric_key or add_key):
        msg.update(key=base64.b64encode(rsa.encrypt(new_symmetric_key or symmetric_key, pub_key)).decode('ascii'))
    if priv_key:
        signature = rsa.sign(json.dumps(msg, sort_keys=True).encode('ascii'), priv_key, 'SHA-512')
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
    if not msg:
        return msg
    if 'enveloped_data' not in msg:
        raise NotValidMessage('msg was not packed')
    if 'signature' in msg:
        if not pub_key:
            raise ValueError('No public key specified to validate signature')
        signature = base64.b64decode(msg.get('signature').encode('ascii'))
        msg_to_validate = copy.deepcopy(msg)
        msg_to_validate.pop('signature')
        rsa.verify(json.dumps(msg_to_validate, sort_keys=True).encode('ascii'), signature, pub_key)

    cipher_key = base64.b64decode(msg.get('key', '').encode('ascii')) or cipher_key
    if cipher_key:
        if not priv_key:
            raise ValueError('No private key specified to decrpyt cipher_key')
        else:
            symmetric_key = rsa.decrypt(cipher_key, priv_key)

    enveloped_data = msg.get('enveloped_data')

    if symmetric_key:
        unloaded_data = decrypt(base64.b64decode(enveloped_data.encode('ascii')), symmetric_key)
    else:
        unloaded_data = base64.b64decode(enveloped_data.encode('ascii'))

    try:
        data = pickle.loads(unloaded_data)
    except pickle.PickleError:
        data = json.loads(unloaded_data)

    return data
