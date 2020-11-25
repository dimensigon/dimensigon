import os
import sys

from dimensigon.dshell import environ
from dimensigon.dshell.history import FileTagHistory
from dimensigon.dshell.network import get, get_parameters_from_path
from dimensigon.utils.helpers import is_valid_uuid


def exit_dshell(msg=None, rc=None):
    print(msg or 'Goodbye!')
    if rc is None:
        rc = 0
    sys.exit(rc)


def get_history(tag, default=None):
    file_history = environ.get('FILE_HISTORY', None)
    if file_history:
        file_history = os.path.expanduser('~/.dshell_history')
        if not os.path.exists(file_history):
            open(file_history, 'w').close()
        history = FileTagHistory(file_history, tag)
    else:
        history = default
    return history


def id2name(view, iden, key='name'):
    view_args = {p: iden for p in get_parameters_from_path(view)}
    if len(view_args) != 1:
        raise ValueError('view has more than 1 parameter to resolve')
    resp = get(view, view_args)
    if resp.code and 200 <= resp.code <= 299:
        if callable(key):
            return key(resp.msg)
        else:
            return resp.msg.get('key')


def name2id(view, name, key='name'):
    view_args = {f'filter[{key}]': name}
    resp = get(view, view_args)
    resp.raise_if_not_ok()
    if len(resp.msg) > 1:
        raise ValueError(f"multiple ids found for '{name}'")
    elif len(resp.msg) == 1:
        return resp.msg[0].get('id', None)
    else:
        raise LookupError(f"'{name}' not found")


def normalize2id(name):
    if not is_valid_uuid(name):
        node_id = name2id('api_1_0.serverlist', name)
    else:
        node_id = name
    return node_id
