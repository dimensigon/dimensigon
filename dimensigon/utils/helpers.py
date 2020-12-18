import datetime as dt
import hashlib
import importlib
import inspect
import itertools
import logging
import os
import random
import re
import string
import sys
import traceback
import typing as t
from collections import Iterable
from contextlib import contextmanager

import netifaces
import requests
import six
from cryptography.fernet import Fernet
from flask import current_app

_LOGGER = logging.getLogger(__name__)


class Singleton(type):
    """ Metaclass that creates a Singleton base type when called. """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls) \
                .__call__(*args, **kwargs)
        return cls._instances[cls]


class AttributeDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


def is_string_types(var):
    return isinstance(var, six.string_types)


def is_iterable(var):
    return isinstance(var, Iterable)


def is_iterable_not_string(var):
    return is_iterable(var) and not is_string_types(var)


UUID_PATTERN = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')


def is_valid_uuid(var):
    # best performance with regular expression compiled and not using re.IGNORECASE
    if isinstance(var, str) and UUID_PATTERN.match(var):
        return True
    else:
        return False


def convert(d):
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = convert(v)
    return AttributeDict(d)


# function to mock datetime.now
def get_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


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
    from dimensigon.domain.entities import Server
    try:
        forwarder = destination.mesh_best_route[0]
    except IndexError:
        forwarder = destination
    else:
        forwarder = Server.query.get(forwarder)

    return f"{protocol}://{forwarder.name}:{forwarder.port}{uri}"


def generate_symmetric_key():
    return Fernet.generate_key()


def encrypt_symmetric(data, key):
    cipher_suite = Fernet(key)
    return cipher_suite.encrypt(data)


def decrypt_symmetric(data, key):
    cipher_suite = Fernet(key)
    return cipher_suite.decrypt(data)


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
        symmetric_key = new_symmetric_key = generate_symmetric_key()
    cipher_data = encrypt_symmetric(data, symmetric_key)
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


def get_entities() -> t.List[t.Tuple['str', t.Any]]:
    from dimensigon.web import db
    entities = []
    for name, cls in inspect.getmembers(sys.modules['dimensigon.domain.entities'],
                                        lambda x: (inspect.isclass(x) and issubclass(x, db.Model))):
        entities.append((name, cls))

    return entities


def get_distributed_entities() -> t.List[t.Tuple['str', t.Any]]:
    from dimensigon.domain.entities.base import DistributedEntityMixin
    entities = []
    for name, cls in inspect.getmembers(sys.modules['dimensigon.domain.entities'],
                                        lambda x: (inspect.isclass(x) and issubclass(x, DistributedEntityMixin))):
        entities.append((name, cls)) if name == cls.__name__ else None


    return sorted(entities, key=lambda x: x[1].order or 99999)


def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_filename_from_cd(cd):
    """
    Get filename from content-disposition
    """
    if not cd:
        return None
    fname = re.findall('filename=(.+)', cd)
    if len(fname) == 0:
        return None
    return fname[0]


def generate_dimension(name):
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from dimensigon.domain.entities import Dimension

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )
    priv_pem = private_key.private_bytes(encoding=serialization.Encoding.PEM,
                                         format=serialization.PrivateFormat.TraditionalOpenSSL,
                                         encryption_algorithm=serialization.NoEncryption())
    pub_pem = private_key.public_key().public_bytes(encoding=serialization.Encoding.PEM,
                                                    format=serialization.PublicFormat.PKCS1)

    return Dimension(name=name, private=priv_pem, public=pub_pem)


def remove_prefix(s, prefix):
    return s[len(prefix):] if s.startswith(prefix) else s


def get_config_from_filename(filename):
    if not os.path.exists(filename):
        raise RuntimeError("%r doesn't exist" % filename)

    ext = os.path.splitext(filename)[1]

    try:
        module_name = '__config__'
        if ext in [".py", ".pyc"]:
            spec = importlib.util.spec_from_file_location(module_name, filename)
        else:
            msg = "configuration file should have a valid Python extension.\n"
            loader_ = importlib.machinery.SourceFileLoader(module_name, filename)
            spec = importlib.util.spec_from_file_location(module_name, filename, loader=loader_)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
    except Exception:
        print("Failed to read config file: %s" % filename, file=sys.stderr)
        traceback.print_exc()
        sys.stderr.flush()
        sys.exit(1)

    return vars(mod)


SQLITE_URL_PREFIX = "sqlite://"


def validate_sqlite_database(dbpath: str) -> bool:
    """Run a quick check on an sqlite database to see if it is corrupt."""
    import sqlite3  # pylint: disable=import-outside-toplevel

    dbpath = dbpath[len(SQLITE_URL_PREFIX):]

    if not os.path.exists(dbpath):
        # Database does not exist yet, this is OK
        return True

    try:
        conn = sqlite3.connect(dbpath)
        conn.cursor().execute("PRAGMA QUICK_CHECK")
        conn.close()
    except sqlite3.DatabaseError:
        # _LOGGER.exception("The database at %s is corrupt or malformed.", dbpath)
        return False

    return True


def get_ips(ipv4=True, ipv6=False) -> t.List[t.Tuple[str, int]]:
    ips = []

    if ipv4:
        ips.extend(list(itertools.chain(
            *[[ip['addr'] for ip in netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])] for iface in
              netifaces.interfaces()])))
    if ipv6:
        iter_ips = itertools.chain(
            *[[ip['addr'] for ip in netifaces.ifaddresses(iface).get(netifaces.AF_INET6, [])] for iface in
              netifaces.interfaces()])

        for ip in iter_ips:
            if ip:
                if '%' in ip:
                    ips.append(ip.rsplit('%')[0])
                else:
                    ips.append(ip)
    return ips


def bind2gate(bind: t.List[str]) -> t.List[t.Tuple[str, int]]:
    from dimensigon import defaults
    specified_gates = set()
    for b in bind:
        if ':' in b:
            gate = b.rsplit(':')
            gate = (gate[0], int(gate[1]))
        else:
            gate = (b, defaults.DEFAULT_PORT)
        if gate[0] == '0.0.0.0':
            ips = get_ips(ipv4=True, ipv6=False)
            for ip in ips:
                specified_gates.update([(ip, int(gate[1]))])
        elif gate[0] == '::':
            ips = get_ips(ipv4=False, ipv6=True)
            for ip in ips:
                specified_gates.update([(ip, int(gate[1]))])
        else:
            specified_gates.update([gate])
    return list(specified_gates)


def clean_string(incoming_string):
    replace_char = '_'
    newstring = incoming_string
    newstring = newstring.replace("!", replace_char)
    newstring = newstring.replace("@", replace_char)
    newstring = newstring.replace("#", replace_char)
    newstring = newstring.replace("$", replace_char)
    newstring = newstring.replace("%", replace_char)
    newstring = newstring.replace("^", replace_char)
    newstring = newstring.replace("&", replace_char)
    newstring = newstring.replace("*", replace_char)
    newstring = newstring.replace("(", replace_char)
    newstring = newstring.replace(")", replace_char)
    newstring = newstring.replace("+", replace_char)
    newstring = newstring.replace("=", replace_char)
    newstring = newstring.replace("?", replace_char)
    newstring = newstring.replace("\'", replace_char)
    newstring = newstring.replace("\"", replace_char)
    newstring = newstring.replace("{", replace_char)
    newstring = newstring.replace("}", replace_char)
    newstring = newstring.replace("[", replace_char)
    newstring = newstring.replace("]", replace_char)
    newstring = newstring.replace("<", replace_char)
    newstring = newstring.replace(">", replace_char)
    newstring = newstring.replace("~", replace_char)
    newstring = newstring.replace("`", replace_char)
    newstring = newstring.replace(":", replace_char)
    newstring = newstring.replace(";", replace_char)
    newstring = newstring.replace("|", replace_char)
    newstring = newstring.replace("\\", replace_char)
    newstring = newstring.replace("/", replace_char)
    newstring = newstring.replace("-", replace_char)
    return newstring


@contextmanager
def session_scope(session=None):
    """Provide a transactional scope around a series of operations."""
    if session is None:
        raise RuntimeError("Session required")

    need_rollback = False
    try:
        yield session
        if session.transaction:
            need_rollback = True
            session.commit()
    except Exception as err:
        _LOGGER.error("Error executing query: %s", err)
        if need_rollback:
            session.rollback()
        raise
    finally:
        session.close()


def format_exception(exc: Exception) -> str:
    return ''.join(traceback.format_exception(exc, exc, exc.__traceback__))


def str_resp(resp: requests.Response):
    try:
        return resp.json()
    except ValueError:
        return resp.text


def get_root(path: str):
    parent_path = os.path.dirname(os.path.abspath(os.path.expanduser(path)))
    if path == parent_path:
        return parent_path
    else:
        return get_root(parent_path)


def remove_root(path: str):
    return path.lstrip(get_root(path))


def get_random_string(length=8):
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(length))