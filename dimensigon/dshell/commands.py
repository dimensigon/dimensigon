import argparse as argparse
import functools
import json
import os

import requests
from prompt_toolkit.completion import merge_completers

from dimensigon import defaults
from dimensigon.domain.entities import ActionType, Scope
from dimensigon.domain.entities.transfer import Status
from dimensigon.dshell import environ
from dimensigon.dshell import environ as env
from dimensigon.dshell.argparse_raise import ParamAction, ExtendAction
from dimensigon.dshell.bootstrap import save_config_file
from dimensigon.dshell.completer import *
from dimensigon.dshell.helpers import name2id, exit_dshell, normalize2id
from dimensigon.dshell.output import dprint
from dimensigon.dshell.prompts.action_template import subprompt as action_prompt
from dimensigon.dshell.prompts.command import subprompt as command_prompt
from dimensigon.dshell.prompts.orchestration import subprompt as orch_prompt
from dimensigon.dshell.utils import clean_none
from dimensigon.utils.helpers import get_now, is_valid_uuid


def status(node, detail=False):
    view_data = {}
    if not detail:
        view_data.update(params='human')
    if not node:
        resp = ntwrk.get('root.healthcheck', view_data=view_data)
        dprint(resp)
    else:
        for n in node:
            dprint(f"### {n}:") if len(node) > 1 else None
            node_id = normalize2id(n)
            resp = ntwrk.get('root.healthcheck', view_data=view_data, headers={'D-Destination': node_id})
            dprint(resp)


def ping(node):
    for n in node:
        dprint(f"### {n}:") if len(node) > 1 else None
        node_id = normalize2id(n)
        resp = ntwrk.post('root.ping', headers={'D-Destination': node_id},
                          json={'start_time': get_now().strftime(defaults.DATETIME_FORMAT)})
        dprint(resp)


def manager_locker_show(node):
    for n in node:
        dprint(f"### {n}:") if len(node) > 1 else None
        node_id = normalize2id(n)
        resp = ntwrk.get('api_1_0.locker', headers={'D-Destination': node_id})
        dprint(resp)


def manager_locker_unlock(scope, node):
    for n in node:
        dprint(f"### {n}:") if len(node) > 1 else None
        node_id = normalize2id(n)
        resp = ntwrk.post('api_1_0.locker_unlock',
                          json={'scope': scope, 'applicant': "", 'force': True},
                          headers={'D-Destination': node_id})
        dprint(resp)


def server_list(name=None, ident=None, detail=None, like=None):
    kwargs = {}
    view_data = dict()
    if name is not None:
        view_data.update({'filter[name]': name})
    if ident:
        view_data.update({'filter[id]': ident})
    if detail:
        view_data.update(params='gates')
    resp = ntwrk.get('api_1_0.serverlist', view_data=view_data, **kwargs)
    if resp.code == 200:
        data = resp.msg or []
        # post process
        filtered_data = []
        if like:
            for server in data:
                if like in server.get('name'):
                    filtered_data.append(server)
        else:
            filtered_data = data
        dprint(filtered_data)
    else:
        dprint(resp)


def server_delete(server_ids):
    normalized_ids = [normalize2id(server_id) for server_id in server_ids]

    if normalized_ids:
        resp = ntwrk.delete('api_1_0.serverlist', json={'server_ids': normalized_ids})
        if resp.ok:
            dprint(f"Server{'s' if len(normalized_ids) > 1 else ''} removed successfully")
        else:
            dprint(resp)
    else:
        dprint("No server no delete")


def server_routes(node, refresh=False):
    resp = None
    if not node:
        node = ['localhost']
    for n in node:
        dprint(f"### {n}:") if len(node) > 1 else None
        if n == 'localhost':
            node_id = None
        else:
            node_id = normalize2id(n)

        kwargs = {}
        if node_id:
            kwargs.update(headers={'D-Destination': node_id})

        if refresh:
            resp = ntwrk.post('api_1_0.routes', json={"discover_new_neighbours": True,
                                                      "check_current_neighbours": True}, **kwargs)
        else:
            resp = ntwrk.get('api_1_0.routes', view_data={'params': 'human'}, **kwargs)
        dprint(resp)


def orch_list(ident=None, name=None, version=None, detail=False, like=None, schema=False):
    kwargs = {}
    view_data = dict()
    if ident is not None:
        view_data.update({'filter[id]': ident})
    if name is not None:
        view_data.update({'filter[name]': name})
    if version is not None:
        view_data.update({'filter[version]': str(version)})
    if detail:
        view_data.update({'params': ['steps', 'vars', 'target', 'action', 'human', 'split_lines']})
    else:
        view_data.update({'params': ['vars', 'target', 'human', 'split_lines']})
    if schema:
        view_data['params'].append('schema')
    resp = ntwrk.get('api_1_0.orchestrationlist', view_data=view_data, **kwargs)
    if resp.code == 200:
        data = resp.msg or []
        # post process
        filtered_data = []
        if like is not None:
            for server in data:
                if like in server.get('name'):
                    filtered_data.append(server)
        else:
            filtered_data = data
        dprint(filtered_data)
    else:
        dprint(resp)


def orch_create(**params):
    orch_prompt({'name': params['name'], 'steps': []},
                changed=True,
                ask_all=params['prompt'], parent_prompt='Δ ')


def orch_copy(**params):
    resp = ntwrk.get('api_1_0.orchestrationresource',
                     view_data={'orchestration_id': params.get('orchestration_id'), 'param': 'split_lines'})

    if resp.ok:
        orch = resp.msg
        orch.pop('target', None)
        orch.pop('params', None)
        orch.pop('id', None)
        orch.pop('version', None)
        orch.pop('last_modified_at', None)
        resp = ntwrk.get('api_1_0.steplist',
                         view_data={'filter[orchestration_id]': params.get('orchestration_id'),
                                    'params': 'split_lines'})
        if resp.ok:
            orch['steps'] = resp.msg

            id2human = {}
            for s in orch['steps']:
                id2human[s.get('id')] = str(len(id2human) + 1)

            # remove unwanted parameters
            for s in orch['steps']:
                s.pop('last_modified_at', None)
                s.pop('created_on', None)
                s.pop('orchestration_id', None)
                s['id'] = id2human[s['id']]
                s['parent_step_ids'] = [id2human[ps] for ps in s['parent_step_ids']]

            orch_prompt(entity=orch, parent_prompt='Δ ')
        else:
            dprint(resp)
    else:
        dprint(resp)


def orch_load(file):
    try:
        orch = json.load(file)
    except Exception as e:
        dprint(e)
    else:
        orch_prompt(orch, parent_prompt='Δ ')


def orch_run(orchestration_id, target, params=None, background=False, scope=None, skip_validation=False):
    data = {}
    data.update(hosts=target, params=params, background=background)
    if scope:
        data.update(scope=scope)
    if skip_validation:
        data.update(skip_validation=skip_validation)

    if not target:
        dprint('No target specified')
    else:
        resp = ntwrk.post('api_1_0.launch_orchestration',
                          view_data={'orchestration_id': orchestration_id, 'params': 'human'}, json=data)
        dprint(resp)


def action_list(ident=None, name=None, version=None, like: str = None, last: int = None):
    kwargs = {}
    view_data = dict()
    if ident:
        view_data.update({'filter[id]': ident})
    if name:
        view_data.update({'filter[name]': name})
    if version:
        view_data.update({'filter[version]': version})
    view_data.update(params='split_lines')
    resp = ntwrk.get('api_1_0.actiontemplatelist', view_data=view_data, **kwargs)
    if resp.code == 200:
        data = resp.msg or []
        # post process
        filtered_data = []
        if like:
            for server in data:
                if like in server.get('name'):
                    filtered_data.append(server)
        else:
            filtered_data = data
        dprint(filtered_data)
    else:
        dprint(resp)


def action_create(name, action_type, prompt):
    action_prompt({'name': name, 'action_type': action_type}, changed=True, ask_all=prompt, parent_prompt='Δ ')


def action_copy(**params):
    resp = ntwrk.get('api_1_0.actiontemplateresource',
                     view_data={'action_template_id': params.get('action_template_id'), 'params': 'split_lines'})

    if resp.ok:
        action = resp.msg
        action.pop('id', None)
        action.pop('version', None)
        action.pop('last_modified_at', None)
        # clean empty fields
        for k, v in dict(action).items():
            if v is None:
                action.pop(k, None)

        action_prompt(entity=action, parent_prompt='Δ ')


def action_load(file):
    try:
        action = json.load(file)
    except Exception as e:
        print(e)
    else:
        action_prompt(action, parent_prompt='Δ ')


def software_add(name, version, file, family=None):
    kwargs = {}
    json_data = dict(name=name, version=version, file=file)
    if family is not None:
        json_data.update(family=family)
    resp = ntwrk.post(view='api_1_0.softwarelist', json=json_data, **kwargs)
    dprint(resp)


def software_delete(software_id):
    kwargs = {}
    resp = ntwrk.delete(view='api_1_0.softwareresource', view_data={'software_id': software_id}, **kwargs)
    dprint(resp)


def software_send(dest_server_id, software_id=None, software=None, version=None, file=None, dest_path=None,
                  background=True, force=False):
    kwargs = {}
    json_data = dict(dest_server_id=dest_server_id, force=force)
    if software_id:
        json_data.update(software_id=software_id)
    elif file:
        json_data.update(file=file)
    else:
        json_data.update(software=software, version=version)
    if dest_path is not None:
        json_data.update(dest_path=dest_path)

    json_data.update(background=background)
    if not background:
        json_data.update(include_transfer_data=True)
    resp = ntwrk.post('api_1_0.send', json=json_data, **kwargs)
    dprint(resp)


def software_list(name=None, version=None, detail=None, like=None):
    kwargs = {}
    view_data = dict()
    if name:
        view_data.update({'filter[name]': name})
    if version:
        view_data.update({'filter[version]': version})
    if detail:
        view_data.update(params='servers')
    resp = ntwrk.get('api_1_0.softwarelist', view_data=view_data, **kwargs)
    if resp.ok:
        data = resp.msg or []
        # post process
        filtered_data = []
        if like:
            for server in data:
                if like in server.get('name'):
                    filtered_data.append(server)
        else:
            filtered_data = data
        dprint(filtered_data)
    else:
        dprint(resp)


def transfer_list(iden=None, status=None, like=None, last=None):
    kwargs = {}
    view_data = dict()
    if iden:
        view_data.update({'filter[id]': iden})
    if status:
        view_data.update({'filter[status]': ','.join(status)})
    resp = ntwrk.get('api_1_0.transferlist', view_data=view_data, **kwargs)
    if resp.ok:
        data = resp.msg or []
        # post process
        filtered_data = []
        if like:
            for server in data:
                if like in server.get('name'):
                    filtered_data.append(server)
        else:
            filtered_data = data
        assert last is None or last > 0, f"Invalid value '{last}'"
        if last is not None and last > 0:
            dprint(filtered_data[-last:])
        else:
            dprint(filtered_data)
    else:
        dprint(resp)


def transfer_cancel(transfer_id):
    kwargs = {}
    data = {'status': 'CANCELLED'}
    resp = ntwrk.patch('api_1_0.transferresource', view_data={'transfer_id': transfer_id}, json=data, **kwargs)
    dprint(resp)


def exec_list(orch=None, server=None, execution_id=None, last=None, asc=None, detail=None):
    kwargs = {}
    view_data = dict()
    view = 'api_1_0.orchexecutionlist'

    if orch:
        view_data.update({'filter[orchestration_id]': orch})

    if server:
        view_data.update({'filter[server_id]': server})

    if execution_id:
        view_data.update({'filter[id]': execution_id})

    # url_parameters
    if detail:
        view_data.update({'params': ['steps', 'human']})
    else:
        view_data.update({'params': ['human']})

    resp = ntwrk.get(view, view_data=view_data, **kwargs)
    if resp.ok:
        data = resp.msg or []
        # post process
        if asc:
            data.sort(key=lambda x: x.get('start_time'))
        else:
            data.sort(key=lambda x: x.get('start_time'), reverse=True)

        if last:
            dprint(data[:last])
        else:
            dprint(data)
    else:
        dprint(resp)


def cmd(command, target, timeout=None, input=None, shell=None):
    if shell:
        command_prompt({'target': target}, ask_all=False if target else True, parent_prompt='Δ')
    else:
        if isinstance(command, list):
            command = ' '.join(command)
        if not command:
            raise ValueError('a command must be specified')
        if not target:
            raise ValueError('target must be specified')
        data = {'command': command, 'target': target}
        if timeout:
            data.update(timeout=timeout)
        if input:
            data.update(input=input.replace('\\n', '\n').replace('\\t', '\t'))
        resp = ntwrk.post('api_1_0.launch_command', view_data={'params': 'human'}, json=data)
        dprint(resp)


def logfed_list():
    kwargs = {}
    resp = ntwrk.get('api_1_0.loglist', view_data={'params': 'human'}, **kwargs)
    dprint(resp.msg if resp.code else str(resp.exception) if str(
        resp.exception) else resp.exception.__class__.__name__)


def logfed_subscribe(src_server_id, target, dst_server_id, include=None, exclude=None, dest_folder=None,
                     recursive=None, mode=None):
    if not is_valid_uuid(src_server_id):
        _src_server_id = name2id('api_1_0.serverlist', src_server_id)
    else:
        _src_server_id = src_server_id
    if not is_valid_uuid(dst_server_id):
        _dst_server_id = name2id('api_1_0.serverlist', dst_server_id)
    else:
        _dst_server_id = dst_server_id
    kwargs = {}
    json_data = dict(src_server_id=_src_server_id, target=target, dst_server_id=_dst_server_id, include=include,
                     exclude=exclude, dest_folder=dest_folder, recursive=recursive, mode=mode)
    json_data = clean_none(json_data)
    resp = ntwrk.post('api_1_0.loglist', json=json_data, **kwargs)
    dprint(resp)


def logfed_unsubscribe(log_id):
    kwargs = {}
    resp = ntwrk.delete('api_1_0.logresource', {'log_id': log_id}, **kwargs)
    dprint(resp)


def manager_catalog_refresh():
    resp = ntwrk.post('api_1_0.catalog_update')
    dprint(resp)


def manager_locker_ignore(ignore: bool, nodes):
    server_ids = [normalize2id(n) for n in nodes]
    resp = ntwrk.post('api_1_0.manager_server_ignore_lock', json={'server_ids': server_ids, 'ignore_on_lock': ignore})
    dprint(resp)


# def locker_lock(**params):
#     pass
#
# def locker_unlock(**params):
#     if params['servers'] is None:
#         resp = get('api_1_0.serverlist')
#         resp.raise_if_not_ok()
#         servers = [s.id for s in resp.msg]
#     else:
#         servers = params['servers']
#
#     for server in servers:
#         resp = post('api_1_0.locker_unlock')

def manager_token(raw=False, expires_time=None):
    resp = ntwrk.get('api_1_0.join_token', view_data=dict(expires_time=expires_time))
    if not raw:
        dprint(resp)
    else:
        if resp.ok:
            dprint(resp.msg['token'])
        else:
            dprint(resp)


def login(username=None, password=None, save=False):
    try:
        ntwrk.login(username, password)
    except requests.exceptions.ConnectionError as e:
        dprint(f"Unable to contact with {environ.get('SCHEME')}://{environ.get('SERVER')}:{environ.get('PORT')}/")
    except Exception as e:
        dprint(str(e))
    else:
        if save:
            save_config_file(os.path.expanduser(env.get('CONFIG_FILE', None)), username=env._username,
                             token=env._refresh_token,
                             server=env.get('SERVER'), port=env.get('PORT'))


def logging_cmd(logger, level):
    logger = logging.getLogger(logger)
    if logger:
        logger.setLevel(level)
    else:
        dprint(f"Logger '{logger}' does not exist")


def env_list():
    for k, v in environ._environ.items():
        dprint(f"{k}={v}")


def env_get(key):
    dprint(f"{environ.get(key, None)}")


def env_set(key, value):
    if isinstance(value, list) and len(value) == 0:
        if '=' in key:
            key, value = key.split('=')
            environ.set(key, value)
        else:
            dprint('invalid value')
    else:
        environ.set(key, ' '.join(value))


def sync_add_file(server: str, file: str, destinations: t.List, dest_folder: str = None):
    server_id = normalize2id(server)
    json_data = {'src_server_id': server_id, 'target': file, 'destinations': []}
    if dest_folder:
        json_data.update(dest_folder=dest_folder)
    for dest in destinations:
        if ':' in dest:
            server, d_folder = dest.split(':', 1)
        else:
            server, d_folder = dest, None
        s_id = normalize2id(server)
        aux = {'dst_server_id': s_id}
        if d_folder:
            aux.update(dest_folder=d_folder)
        json_data['destinations'].append(aux)

    resp = ntwrk.post('api_1_0.filelist', json=json_data)
    dprint(resp)


def sync_add_destination(file_id: str, destinations: t.List):
    json_data = []
    for dest in destinations:
        if ':' in dest:
            server, d_folder = dest.split(':', 1)
        else:
            server, d_folder = dest, None
        s_id = normalize2id(server)
        aux = {'dst_server_id': s_id}
        if d_folder:
            aux.update(dest_folder=d_folder)
        json_data.append(aux)
    resp = ntwrk.post('api_1_0.fileserverassociationlist', view_data={'file_id': file_id}, json=json_data)
    dprint(resp)


def sync_delete_file(file_id):
    resp = ntwrk.delete('api_1_0.fileresource', view_data={'file_id': file_id})
    dprint(resp)


def sync_delete_destination(file_id: str, destinations: t.List):
    json_data = []
    for dest in destinations:
        s_id = normalize2id(dest)
        aux = {'dst_server_id': s_id}
        json_data.append(aux)
    resp = ntwrk.delete('api_1_0.fileserverassociationlist', view_data={'file_id': file_id}, json=json_data)
    dprint(resp)


def sync_list(ident, source_server, detail):
    kwargs = {}
    view_data = dict()
    if ident:
        view_data.update({'filter[id]': ident})
    if source_server:
        view_data.update({'filter[src_server_id]': normalize2id(source_server)})
    if detail:
        view_data.update({'params': ['destinations', 'human']})
    else:
        view_data.update({'params': ['human']})
    resp = ntwrk.get('api_1_0.filelist', view_data=view_data, **kwargs)
    dprint(resp)


def vault_list_scopes():
    resp = ntwrk.get('api_1_0.vaultlist', dict(params='scopes'))
    dprint(resp)


def vault_list_vars(scope='global'):
    resp = ntwrk.get('api_1_0.vaultlist', dict(params='vars', scope=scope))
    dprint(resp)


def vault_read(variable, scope='global'):
    resp = ntwrk.get('api_1_0.vaultresource', dict(name=variable, scope=scope))
    if resp.ok:
        dprint(resp['value'])
    else:
        dprint(resp)


def vault_write(variable, value, scope='global'):
    resp = ntwrk.put('api_1_0.vaultresource', dict(name=variable, scope=scope), json={'value': value})
    dprint(resp)


def vault_delete(variable, scope='global'):
    resp = ntwrk.delete('api_1_0.vaultresource', dict(name=variable, scope=scope))
    dprint(resp)


nested_dict = {
    'action': {
        'list': [{'argument': '--version', 'action': 'store', 'type': int,
                  'completer': action_ver_completer},
                 [{'argument': '--id', 'dest': 'ident', 'completer': action_completer},
                  {'argument': '--name', 'completer': action_name_completer},
                  {'argument': '--like'}],
                 action_list
                 ],
        'create': [{'argument': 'name'},
                   {'argument': 'action_type', 'choices': [at.name for at in ActionType if at.name != 'NATIVE']},
                   {'argument': '--prompt', 'action': "store_true",
                    'help': 'prompts for every action parameter to be set by user'},
                   action_create],
        'copy': [{'argument': 'action_template_id', 'completer': action_completer},
                 action_copy],
        'load': [{'argument': 'file', 'type': argparse.FileType('r')},
                 action_load],
    },
    'cmd': [{'argument': 'command', 'nargs': '*'},
            {'argument': '--shell', 'action': 'store_true'},
            {'argument': '--target', 'action': ExtendAction, 'nargs': "+",
             'completer': merge_completers([server_completer, granule_completer])},
            {'argument': '--timeout', 'type': int, 'help': 'timeout in seconds to wait for command to terminate'},
            {'argument': '--input'},
            cmd],
    "env": {
        "list": [env_list],
        "get": [{'argument': 'key', 'completer': DshellWordCompleter(environ._environ.keys())},
                env_get],
        "set": [{'argument': 'key', 'completer': DshellWordCompleter(environ._environ.keys())},
                {'argument': 'value', 'nargs': '*'},
                env_set]},
    'exec': {
        'list': [{'argument': '--orch', 'completer': orch_completer},
                 {'argument': '--id', 'dest': 'execution_id'},
                 {'argument': '--server', 'completer': server_completer},
                 {'argument': '--last', 'metavar': 'N', 'type': int, 'help': "shows last N orchestrations"},
                 {'argument': '--asc', 'action': 'store_true'},
                 {'argument': '--detail', 'action': 'store_true'},
                 exec_list]
    },
    'exit': [exit_dshell],
    'logfed': {
        'subscribe': {'log': [{'argument': 'src_server_id',
                               'metavar': 'source_server',
                               'help': 'source server to get the logs from',
                               'completer': server_name_completer},
                              {'argument': 'target',
                               'metavar': 'file',
                               'help': 'log file to watch out'},
                              {'argument': 'dst_server_id',
                               'metavar': 'destination_server',
                               'help': 'destination server to get the logs from',
                               'completer': server_name_completer},
                              {'argument': '--mode', 'choices': ['REPO_MIRROR', 'REPO_ROOT', 'MIRROR'],
                               'help': 'defines where the log will be sent on destination. REPO_MIRROR send the '
                                       'file inside the dest LOG folder and mantains absolute path from origin. '
                                       'REPO_ROOT sends the file inside the dest LOG without mantaining origin'
                                       '\'s path. MIRROR preserves source path and tries to create at dest'},
                              {'argument': '--dest_folder',
                               'help': 'destination folder to send logs. If not specified, '
                                       'default mode REPO_MIRROR is used'},
                              logfed_subscribe
                              ],
                      'dir': [{'argument': 'target',
                               'metavar': 'folder',
                               'help': 'folder to watch out for files to send'},
                              {'argument': 'src_server_id',
                               'metavar': 'source_server_id',
                               'help': 'source server to get the logs from',
                               'completer': server_completer},
                              {'argument': 'dst_server_id',
                               'metavar': 'destination_server_id',
                               'help': 'source server to get the logs from',
                               'completer': server_completer},
                              {'argument': '--include',
                               'help': 'regular expression used to filter which '
                                       'files and folders should subscribe'},
                              {'argument': '--exclude',
                               'help': 'regular expression used to filter which files and folders '
                                       'should NOT subscribe'},
                              {'argument': '--recursive',
                               'help': 'enters in each folder to find files to send'},
                              {'argument': '--mode', 'choices': ['REPO_MIRROR', 'REPO_ROOT', 'MIRROR'],
                               'help': 'defines where the log will be sent on destination. REPO_MIRROR send the '
                                       'file inside the dest LOG folder and mantains absolute path from origin. '
                                       'REPO_ROOT sends the file inside the dest LOG without mantaining origin'
                                       '\'s path. MIRROR preserves source path and tries to create at dest'},
                              {'argument': '--dest_folder',
                               'help': 'destination folder to send logs. If not specified, '
                                       'default mode REPO_MIRROR is used'},
                              logfed_subscribe]
                      },
        'unsubscribe': [{'argument': 'log_id', 'completer': logfed_completer},
                        logfed_unsubscribe],
        'list': [logfed_list],
    },
    "logging": [{'argument': 'logger', 'completer': logger_completer},
                {'argument': 'level', 'choices': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']},
                logging_cmd],
    "login": [{'argument': 'username', 'nargs': '?'},
              {'argument': '--save', 'action': 'store_true'},
              login],
    "manager": {
        "catalog": {"refresh": [manager_catalog_refresh]},
        "locker": {"ignore": [{'argument': 'nodes', 'metavar': 'NODE', 'nargs': '+',
                               'completer': server_name_completer},
                              functools.partial(manager_locker_ignore, True)],
                   "unignore": [{'argument': 'nodes', 'metavar': 'NODE', 'nargs': '+',
                                 'completer': server_name_completer},
                                functools.partial(manager_locker_ignore, False)],
                   'show': [{'argument': 'node', 'nargs': '+', 'completer': server_name_completer},
                            manager_locker_show],
                   'unlock': [{'argument': 'scope', 'choices': [s.name for s in Scope]},
                              {'argument': 'node', 'nargs': '+', 'completer': server_name_completer},
                              manager_locker_unlock]
                   },
        "token": [{'argument': 'expires_time', 'nargs': '?', 'metavar': 'MINUTES',
                   'help': 'Join token expire time in minutes'},
                  {'argument': '--raw', 'action': 'store_true'},
                  manager_token], },
    'orch': {
        'list': [
            {'argument': '--version', 'action': 'store', 'type': int,
             'completer': orch_ver_completer},
            [{'argument': '--detail', 'action': 'store_true'},
             {'argument': '--schema', 'action': 'store_true'}],
            [{'argument': '--like'},
             {'argument': '--id', 'dest': 'ident', 'completer': orch_completer},
             {'argument': '--name', 'completer': orch_name_completer}],
            orch_list
        ],
        'create': [
            {'argument': 'name'},
            {'argument': '--prompt', 'action': "store_true",
             'help': 'ask for every orch parameter one by one'},
            orch_create],
        'copy': [
            {'argument': 'orchestration_id', 'completer': orch_completer},
            orch_copy],
        'load': [
            {'argument': 'file', 'type': argparse.FileType('r')},
            orch_load],
        'run': [
            {'argument': 'orchestration_id', 'completer': orch_completer},
            {'argument': 'target', 'metavar': 'TARGET=VALUE', 'action': DictAction, 'nargs': "+",
             'completer': merge_completers([server_name_completer, granule_completer]),
             'help': "Run the orch agains the specified target. If no target specified, hosts will be added to "
                     "'all' target. Example: --target node1 node2 backend=node2,node3 "},
            {'argument': '--param', 'dest': 'params', 'metavar': 'PARAM:VALUE', 'action': ParamAction, "nargs": "+",
             'help': 'Parameters passed to the orchestration. Param must start with a lowercase character and ' \
                     'contain only hyphens (-), underscores (_), lowercase characters, and numbers. ' \
                     'Example: --params="string-key:\'string-value\'" --param="integer-key:12345" ' \
                     '--param="list-key:[1,2,3]" --param="dict-key:{\'foo\': 1}"'},
            {'argument': '--no-wait', 'dest': 'background', 'action': 'store_true'},
            {'argument': '--skip-validation', 'action': 'store_false',
             'help': 'skips input validation and runs orchestration regardless of schema definition'},
            {'argument': '--vault-scope', 'dest': 'scope',
             'help': 'scope used for fetching vault data. defaults to \'global\''},
            orch_run],
    },
    'ping': [{'argument': 'node', 'nargs': '+', 'completer': server_name_completer}, ping],
    'server': {
        'list': [{'argument': '--detail', 'action': 'store_true'},
                 [{'argument': '--like'},
                  {'argument': '--name', 'completer': server_name_completer},
                  {'argument': '--id', 'dest': 'ident', 'completer': server_completer},
                  # {'argument': '--last', 'action': 'store', 'type': int}
                  ],
                 server_list
                 ],
        'delete': [
            {'argument': 'server_ids', 'metavar': 'NODE', 'nargs': '+', 'completer': server_name_completer,
             'help': 'Node to be deleted'},
            server_delete],
        'routes': [{'argument': 'node', 'nargs': '*', 'completer': server_name_completer},
                   {'argument': '--refresh', 'action': 'store_true'},
                   server_routes],
    },
    'software': {
        'add': [{'argument': 'name'},
                {'argument': 'version'},
                {'argument': 'file'},
                {'argument': '--family', 'completer': software_family_completer},
                software_add],
        'delete': [{'argument': 'software_id', 'completer': software_completer},
                   software_delete],
        'list': [{'argument': '--version', 'action': 'store', 'type': int,
                  'completer': software_ver_completer},
                 {'argument': '--detail', 'action': 'store_true'},
                 [{'argument': '--json', 'action': 'store_true'},
                  {'argument': '--table', 'action': 'store_true'}],
                 [{'argument': '--like'},
                  {'argument': '--id', 'completer': software_completer},
                  {'argument': '--name', 'completer': software_name_completer}],
                 software_list
                 ],
        'send': [{'argument': 'software_id', 'completer': software_completer},
                 {'argument': 'dest_server_id', 'completer': server_completer},
                 {'argument': '--dest_path'},
                 {'argument': '--foreground', 'action': 'store_false', 'dest': 'background', 'default': True},
                 {'argument': '--force', 'action': 'store_true'},
                 software_send], },
    'status': [{'argument': 'node', 'nargs': '*', 'completer': server_name_completer},
               {'argument': '--detail', 'action': 'store_true'}, status],
    'sync': {
        'list': [{'argument': '--id', 'dest': 'ident', 'completer': file_completer},
                 {'argument': '--server', 'dest': 'source_server', 'completer': server_name_completer},
                 {'argument': '--detail', 'action': 'store_true'},
                 sync_list
                 ],
        'add': {'file': [{'argument': 'server', 'completer': server_name_completer},
                         {'argument': 'file'},
                         {'argument': 'destinations', 'metavar': 'SERVER[:FOLDER]', "nargs": "+",
                          'completer': server_name_completer},
                         {'argument': '--dest_folder',
                          'help': 'default folder used for syncing file. If no dest_folder, mirror '
                                  'copy will be used'},
                         sync_add_file],
                'destination': [{'argument': 'file_id', 'completer': file_completer},
                                {'argument': 'destinations', 'metavar': 'SERVER[:FILE]', "nargs": "+",
                                 'completer': server_name_completer},
                                sync_add_destination]},
        'delete': {'file': [{'argument': 'file_id', 'completer': file_completer},
                            sync_delete_file],
                   'destination': [{'argument': 'file_id', 'completer': file_completer},
                                   {'argument': 'destinations', "nargs": "+", 'completer': file_dest_completer},
                                   sync_delete_destination]
                   },

    },
    'transfer': {
        'cancel': [{'argument': 'transfer_id'},
                   transfer_cancel],
        'list': [
            {'argument': '--status', 'action': "append", 'nargs': '+', 'choices': [s.name for s in Status]},
            [{'argument': '--id'},
             {'argument': '--last', 'action': 'store', 'type': int}, ],
            transfer_list
        ]},
    'vault': {
        'list': {'scopes': [vault_list_scopes],
                 'vars': [{'argument': '--scope'}, vault_list_vars]},
        'read': [{'argument': 'variable'},
                 {'argument': ['--scope', '-s'], 'default': 'global'},
                 vault_read],
        'write': [{'argument': 'variable'},
                  {'argument': 'value'},
                  {'argument': ['--scope', '-s'], 'default': 'global'},
                  vault_write],
        'delete': [{'argument': 'variable'},
                   {'argument': ['--scope', '-s'], 'default': 'global'},
                   vault_delete]

    }

}
