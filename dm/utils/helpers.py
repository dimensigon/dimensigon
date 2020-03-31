import configparser
import datetime
import hashlib
import inspect
import itertools
import logging
import os
import platform
import re
import sys
import typing as t
from collections import Iterable, ChainMap

import netifaces
import six
import yaml
from cryptography.fernet import Fernet
from flask import current_app

import dm.defaults as d
from dm import defaults


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


def get_distributed_entities() -> t.List[t.Tuple['str', t.Any]]:
    from dm.domain.entities.base import DistributedEntityMixin
    entities = []
    for name, cls in inspect.getmembers(sys.modules['dm.domain.entities'],
                                        lambda x: (inspect.isclass(x) and issubclass(x, DistributedEntityMixin))):
        entities.append((name, cls))

    return sorted(entities, key=lambda x: x[1].order or 99999)


def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def load_config_yaml():
    filename = os.path.join(d.HOME, d.CONFIG_FILE)
    with open(filename) as fd:
        config = yaml.load(fd, Loader=yaml.FullLoader)
    # if 'host' in config and config['host'].strip() == '0.0.0.0':
    #     config['host'] = '127.0.0.1'

    return config


def save_config_yaml(config):
    filename = os.path.join(d.HOME, d.CONFIG_FILE)
    with open(filename, 'w') as fd:
        yaml.dump(config, fd)


def update_config_yaml(param, value):
    filename = os.path.join(d.HOME, d.CONFIG_FILE)
    yaml_config = load_config_yaml()
    attributes = param.split('.')
    selected = yaml_config
    i = 0
    while i < (len(attributes) - 1):
        selected = selected[attributes[i]]
        i += 1
    selected.update({attributes[-1]: value})
    save_config_yaml(yaml_config)


def load_config_wsgi():
    filename = os.path.join(d.HOME, d.WSGI_FILE)
    config = configparser.ConfigParser()
    # if not os.path.exists(filename):
    #     file = os.path.join(os.getcwd(), filename)
    # else:
    r = config.read(filename)
    protocol = None
    if len(r) == 0:
        raise FileNotFoundError(f"unable to find file '{filename}'")
    if 'uwsgi' not in config:
        raise ValueError("Section 'uwsgi' not found in file")
    if 'https' in config['uwsgi']:
        raise NotImplemented('https not supported')
    else:
        if 'http' in config['uwsgi']:
            protocol = 'http'
            ip, port = config['uwsgi']['http'].split(':')

    if ip is None or ip == '*' or ip == '0.0.0.0':
        ip = '127.0.0.1'
    port = int(port) if port else defaults.PORT
    return {'dm': {'protocol': protocol, 'host': ip, 'port': port, 'venv': config.get('venv', None)}}


def collect_initial_config():
    config = ChainMap(load_config_yaml())
    # if platform.system() == 'Windows':
    #     p = find_process_by_name('flask')
    #     if not p:
    #         p = find_python_file_executed('dimensigon.py')
    #     args = p.cmdline()
    #     host_op = '-h' if '-h' in args else '--host' if '--host' in args else None
    #     if host_op:
    #         ip = args[args.index(host_op) + 1]
    #     else:
    #         ip = '127.0.0.1'
    #     port_op = '-p' if '-p' in args else '--port' if '--port' in args else None
    #     if port_op:
    #         port = args[args.index(port_op) + 1]
    #     else:
    #         if 'FLASK_RUN_PORT' in p.environ():
    #             port = p.environ()['FLASK_RUN_PORT']
    #         else:
    #             port = 5000
    #     protocol = 'https' if '--cert' in args else 'http'
    #
    #     config = {'protocol': protocol, 'ip': ip, 'port': port, 'venv': p.environ().get('VIRTUAL_ENV', None)}
    if platform.system() == 'Linux':
        config = config.new_child(load_config_wsgi())

    return config


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
    from dm.domain.entities import Dimension

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


def get_ips_listening_for() -> t.List[t.Tuple[str, int]]:
    from gunicorn_conf import bind
    gates = []
    for b in bind:
        dns_or_ip, port = b.split(':')
        if dns_or_ip == '0.0.0.0':
            ips = list(itertools.chain(
                *[[ip['addr'] for ip in netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])] for iface in
                  netifaces.interfaces()]))
            gates.extend([(ip, port) for ip in ips])
        else:
            gates.append((dns_or_ip, port))
    return gates
