import base64
import logging
import pickle
import typing as t
import datetime

from cryptography.fernet import Fernet
import rsa as rsa
from flask import current_app

from dm.framework.interfaces.entity import Id

if t.TYPE_CHECKING:
    from dm.domain.entities import Server


class AttributeDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


# function to mock datetime.now
def get_now() -> datetime.datetime:
    return datetime.datetime.now()


def convert(d):
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = convert(v)
    return AttributeDict(d)


def str_to_key(id_: str):
    key = []
    for x in id_.split('.'):
        try:
            x = int(x)
        except ValueError:
            pass
        finally:
            key.append(x)
    return tuple(key) if len(key) > 1 else key[0]


def key_to_str(key: Id):
    if isinstance(key, t.Sequence):
        id_ = '.'.join([str(i) for i in key])
    else:
        id_ = str(key)
    return id_


def generate_url(destination: 'Server', uri, protocol='https'):
    try:
        forwarder: 'Server' = destination.route[0]
    except IndexError:
        forwarder = destination

    return f"{protocol}://{forwarder.name}:{forwarder.port}{uri}"


def encrypt(data: bytes, symmetric_key: bytes = None) -> \
        t.Tuple[bytes, t.Optional[bytes]]:
    """

    Parameters
    ----------
    data:
        data to encrypt.
    symmetric_key:
        symmetric key used for encrypting data. If set, cipher_key must be None

    Returns
    -------

    """
    new_symmetric_key = None
    if not symmetric_key:
        symmetric_key = new_symmetric_key = Fernet.generate_key()
    cipher_suite = Fernet(symmetric_key)
    cipher_data = cipher_suite.encrypt(data)
    return cipher_data, new_symmetric_key


def decrypt(cipher_text: bytes, symmetric_key: bytes) -> bytes:
    """

    Parameters
    ----------
    cipher_text:
        text to decrypt
    cipher_key:
        symmetric_key encrypted. If specified symmetric_key must be None (default)
    symmetric_key:
        symmetric_key. If specified cipher_token must be None (default)
    key:
        key used for decryption of cipher_key

    Returns
    -------
    decrypted data
    """
    cipher_suite = Fernet(symmetric_key)
    dumped_data = cipher_suite.decrypt(cipher_text)
    return dumped_data


def get_logger(self=None):
    if self:
        name = '.'.join([
            self.__module__,
            self.__name__
        ])
    else:
        name = None
    try:
        current_app.logger
    except RuntimeError:
        logger = logging.getLogger(name)
    else:
        logger = current_app.logger
    return logger
