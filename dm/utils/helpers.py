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


def encode(*args, key=None, **kwargs):
    cipher_text = pickle.dumps(args[0] if len(args) else kwargs)
    cipher_key = b''
    if key:
        token = Fernet.generate_key()
        cipher_suite = Fernet(token)
        cipher_text = cipher_suite.encrypt(cipher_text)
        cipher_key = rsa.encrypt(token, key)
    return base64.b64encode(cipher_text), base64.b64encode(cipher_key)


def decode(cipher_text, cipher_token=None, key=None):
    dumped_data = cipher_text_decoded = base64.b64decode(cipher_text)
    if key:
        token = rsa.decrypt(base64.b64decode(cipher_token), key)
        cipher_suite = Fernet(token)
        dumped_data = cipher_suite.decrypt(cipher_text_decoded)
    return pickle.loads(dumped_data)


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
