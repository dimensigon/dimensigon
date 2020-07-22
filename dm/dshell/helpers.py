import os
import sys

from dm.dshell import environ
from dm.dshell.history import FileTagHistory
from dm.dshell.network import get, get_parameters_from_path


def exit_dshell(msg='Goodbye!', rc=0):
    print(msg)
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
    if resp.ok:
        if len(resp.msg) > 1:
            raise ValueError('multiple ids found')
        return resp.msg[0].get('id', None)
