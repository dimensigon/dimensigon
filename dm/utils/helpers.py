import datetime
import hashlib
import inspect
import logging
import sys
import typing as t
from collections import Iterable

import six
from cryptography.fernet import Fernet
from flask import current_app
from flask_sqlalchemy import Model


class AttributeDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


def is_string_types(var):
    return isinstance(var, six.string_types)


def is_iterable(var):
    return isinstance(var, Iterable)


def is_iterable_not_string(var):
    return is_iterable(var) and not is_string_types(var)


def convert(d):
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = convert(v)
    return AttributeDict(d)


# function to mock datetime.now
def get_now() -> datetime.datetime:
    return datetime.datetime.now()


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


def key_to_str(key):
    if isinstance(key, t.Sequence):
        id_ = '.'.join([str(i) for i in key])
    else:
        id_ = str(key)
    return id_


def generate_url(destination, uri, protocol='https'):
    from dm.domain.entities import Server
    try:
        forwarder = destination.mesh_best_route[0]
    except IndexError:
        forwarder = destination
    else:
        forwarder = Server.query.get(forwarder)

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


def get_distributed_entities() -> t.List[t.Tuple['str', t.Type[Model]]]:
    from dm.domain.entities.base import DistributedEntityMixin
    entities = []
    for name, cls in inspect.getmembers(sys.modules['dm.domain.entities'], inspect.isclass):
        if issubclass(cls, DistributedEntityMixin):
            entities.append((name, cls))
    return entities


def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()
