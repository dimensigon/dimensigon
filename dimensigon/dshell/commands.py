import argparse as argparse
import functools
import json
import os
import uuid

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
from dimensigon.dshell.helpers import name2id, exit_dshell
from dimensigon.dshell.output import dprint
from dimensigon.dshell.prompts.action_template import subprompt as action_prompt
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
            if not is_valid_uuid(n):
                node_id = name2id('api_1_0.serverlist', n)
            else:
                node_id = n
            resp = ntwrk.get('root.healthcheck', view_data=view_data, headers={'D-Destination': node_id})
            dprint(resp)


def ping(node):
    for n in node:
        dprint(f"### {n}:") if len(node) > 1 else None
        if not is_valid_uuid(n):
            node_id = name2id('api_1_0.serverlist', n)
        else:
            node_id = n
        resp = ntwrk.post('root.ping', headers={'D-Destination': node_id},
                          json={'start_time': get_now().strftime(defaults.DATETIME_FORMAT)})
        dprint(resp)


def locker_show(node):
    for n in node:
        dprint(f"### {n}:") if len(node) > 1 else None
        if not is_valid_uuid(n):
            node_id = name2id('api_1_0.serverlist', n)
        else:
            node_id = n
        resp = ntwrk.get('api_1_0.locker', headers={'D-Destination': node_id})
        dprint(resp)


def locker_unlock(scope, node):
    for n in node:
        dprint(f"### {n}:") if len(node) > 1 else None
        if not is_valid_uuid(n):
            node_id = name2id('api_1_0.serverlist', n)
        else:
            node_id = n
        resp = ntwrk.post('api_1_0.locker_unlock',
                          json={'scope': scope, 'applicant': "", 'force': True},
                          headers={'D-Destination': node_id})
        dprint(resp)


def server_list(name=None, iden=None, detail=None, like=None):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    view_data = dict()
    if name is not None:
        view_data.update({'filter[name]': name})
    if iden:
        view_data.update({'filter[id]': iden})
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


def server_delete(server_id):
    try:
        uuid.UUID(server_id)
    except Exception:
        not_an_uuid = True
    else:
        not_an_uuid = False
    if not_an_uuid:
        server_id = name2id('api_1_0.serverlist', server_id)
    resp = ntwrk.delete('api_1_0.serverresource', view_data={'server_id': server_id})
    if resp.ok:
        dprint("Server removed succesfully")
    else:
        dprint(resp)


def server_routes(refresh=False):
    resp = None
    if refresh:
        resp = ntwrk.post('api_1_0.routes', json={"discover_new_neighbours": True,
                                                  "check_current_neighbours": True})
    if resp is None or (resp and resp.ok):
        resp = ntwrk.get('api_1_0.routes', view_data={'params': 'human'})
    dprint(resp)


def orch_list(**params):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    view_data = dict()
    if params.get('id', None):
        view_data.update({'filter[id]': params['id']})
    if params.get('name'):
        view_data.update({'filter[name]': params['name']})
    if params.get('version', None):
        view_data.update({'filter[version]': str(params['version'])})
    if params.get('detail', None):
        view_data.update({'params': ['steps', 'vars', 'target', 'action', 'human']})
    else:
        view_data.update({'params': ['vars', 'target', 'human']})
    resp = ntwrk.get('api_1_0.orchestrationlist', view_data=view_data, **kwargs)
    if resp.code == 200:
        data = resp.msg or []
        # post process
        filtered_data = []
        if params.get('like', None):
            for server in data:
                if params.get('like') in server.get('name'):
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
                     view_data={'orchestration_id': params.get('orchestration_id')})

    if resp.ok:
        orch = resp.msg
        orch.pop('target', None)
        orch.pop('params', None)
        orch.pop('id', None)
        orch.pop('version', None)
        orch.pop('last_modified_at', None)
        resp = ntwrk.get('api_1_0.steplist',
                         view_data={'filter[orchestration_id]': params.get('orchestration_id')})
        if resp.ok:
            orch['steps'] = resp.msg

            # remove unwanted parameters
            for s in orch['steps']:
                s.pop('last_modified_at', None)
                s.pop('created_on', None)
                s.pop('orchestration_id', None)

            orch_prompt(entity=orch, parent_prompt='Δ ')


def orch_load(file):
    try:
        orch = json.load(file)
    except Exception as e:
        print(e)
    else:
        orch_prompt(orch, parent_prompt='Δ ')


def orch_run(orchestration_id, **params):
    if not params['hosts']:
        print('No target specified')
        return
    resp = ntwrk.post('api_1_0.launch_orchestration',
                      view_data={'orchestration_id': orchestration_id, 'params': 'human'}, json=params)
    dprint(resp)


def action_list(iden=None, name=None, version=None, like: str = None, last: int = None):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    view_data = dict()
    if iden:
        view_data.update({'filter[id]': iden})
    if name:
        view_data.update({'filter[name]': name})
    if version:
        view_data.update({'filter[version]': version})
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


#
# def action_modify(**params):
#     resp = ntwrk.get('api_1_0.actiontemplateresource',
#                      view_data={'action_template_id': params.get('action_template_id')})
#     if resp.code == 200:
#         action_prompt(entity=resp.msg, parent_prompt='Δ ')


def action_load(file):
    try:
        action = json.load(file)
    except Exception as e:
        print(e)
    else:
        action_prompt(action, parent_prompt='Δ ')


def software_add(name, version, file, family=None):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    json_data = dict(name=name, version=version, file=file)
    if family is not None:
        json_data.update(family=family)
    resp = ntwrk.post(view='api_1_0.softwarelist', json=json_data, **kwargs)
    dprint(resp)


def software_send(dest_server_id, software_id=None, software=None, version=None, file=None, dest_path=None,
                  background=True, force=False):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    json_data = dict(dest_server_id=dest_server_id, dest_path=dest_path, force=force)
    if software_id:
        json_data.update(software_id=software_id)
    elif file:
        json_data.update(file=file)
    else:
        json_data.update(software=software, version=version)

    if not background:
        json_data.update(include_transfer_data=True)
    resp = ntwrk.post('api_1_0.send', json=json_data, **kwargs)
    dprint(resp)


def software_list(name=None, version=None, detail=None, like=None):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
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


def transfer_list(iden=None, status=None, like=None):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
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
        dprint(filtered_data)
    else:
        dprint(resp)


def transfer_cancel(transfer_id):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    data = {'status': 'CANCELED'}
    resp = ntwrk.patch('api_1_0.transferresource', view_data={'transfer_id': transfer_id}, json=data, **kwargs)
    dprint(resp)


def exec_list(orch=None, server=None, execution_id=None, last=None, asc=None, detail=None):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
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


def cmd(command, hosts, timeout=None, input=None):
    if isinstance(command, list):
        command = ' '.join(command)

    data = {'command': command, 'hosts': hosts}
    if timeout:
        data.update(timeout=timeout)
    if input:
        data.update(input=input.replace('\\n', '\n').replace('\\t', '\t'))
    resp = ntwrk.post('api_1_0.launch_command', view_data={'params': 'human'}, json=data)
    dprint(resp)


def logfed_list():
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    resp = ntwrk.get('api_1_0.loglist', view_data={'params': 'human'}, **kwargs)
    dprint(resp.msg if resp.code else str(resp.exception) if str(
        resp.exception) else resp.exception.__class__.__name__)


def logfed_subscribe(src_server_id, target, dest_server_id, include=None, exclude=None, dest_folder=None,
                     recursive=None, mode=None):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    json_data = dict(src_server_id=src_server_id, target=target, dest_server_id=dest_server_id, include=include,
                     exclude=exclude, dest_folder=dest_folder, recursive=recursive, mode=mode)
    json_data = clean_none(json_data)
    resp = ntwrk.post('api_1_0.loglist', json=json_data, **kwargs)
    dprint(resp)


def logfed_unsubscribe(log_id):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    resp = ntwrk.delete('api_1_0.logresource', {'log_id': log_id}, **kwargs)
    dprint(resp)


def manager_catalog_refresh():
    resp = ntwrk.post('api_1_0.catalog_update')
    dprint(resp)


def manager_locker_ignore(ignore: bool, server_ids):
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

def token(raw=False):
    resp = ntwrk.get('api_1_0.join_token')
    if not raw:
        dprint(resp)
    else:
        if resp.ok:
            dprint(resp.msg['token'])
        else:
            dprint(resp)


def manager_login(username=None, password=None):
    try:
        ntwrk.login(username, password)
    except requests.exceptions.ConnectionError as e:
        dprint(f"Unable to contact with {environ.get('SCHEME')}://{environ.get('SERVER')}:{environ.get('PORT')}/")
    except Exception as e:
        dprint(str(e))


def manager_save_login():
    save_config_file(os.path.expanduser(env.get('CONFIG_FILE', None)), username=env._username, token=env._refresh_token, server=env.get('SERVER'), port=env.get('PORT'))

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


nested_dict = {
    'status': [{'argument': 'node', 'nargs': '*', 'completer': server_completer},
               {'argument': '--detail', 'action': 'store_true'}, status],
    'ping': [{'argument': 'node', 'nargs': '+', 'completer': server_completer}, ping],
    'server': {
        'list': [{'argument': '--detail', 'action': 'store_true'},
                 [{'argument': '--json', 'action': 'store_true'},
                  {'argument': '--table', 'action': 'store_true'}],
                 [{'argument': '--like'},
                  {'argument': '--name', 'completer': server_name_completer},
                  {'argument': '--id', 'dest': 'iden', 'completer': server_completer},
                  # {'argument': '--last', 'action': 'store', 'type': int}
                  ],
                 server_list
                 ],
        'delete': [
            {'argument': 'server_id', 'metavar': 'NODE', 'completer': server_completer, 'help': 'Node to be deleted'},
            server_delete],
        'routes': [{'argument': '--refresh', 'action': 'store_true'},
                   server_routes],
    },
    'orch': {
        'list': [{'argument': '--version', 'action': 'store', 'type': int,
                  'completer': orch_ver_completer},
                 {'argument': '--detail', 'action': 'store_true'},
                 [{'argument': '--json', 'action': 'store_true'},
                  {'argument': '--table', 'action': 'store_true'}],
                 [{'argument': '--like'},
                  {'argument': '--id', 'completer': orch_completer},
                  {'argument': '--name', 'completer': orch_name_completer}],
                 orch_list
                 ],
        'create': [{'argument': 'name'},
                   {'argument': '--prompt', 'action': "store_true",
                    'help': 'ask for every orch parameter one by one'},
                   orch_create],
        'copy': [{'argument': 'orchestration_id', 'completer': orch_completer},
                 orch_copy],
        'load': [{'argument': 'file', 'type': argparse.FileType('r')},
                 orch_load],
        'run': [{'argument': 'orchestration_id', 'completer': orch_completer},
                {'argument': '--target', 'metavar': 'TARGET=VALUE', 'action': DictAction, 'nargs': "+", 'dest': 'hosts',
                 'completer': merge_completers([server_completer, granule_completer]),
                 'help': "Run the orch agains the specified target. If no target specified, hosts will be added to "
                         "'all' target. Example: --target node1 node2 backend=node2,node3 "},
                {'argument': '--param', 'metavar': 'PARAM=VALUE', 'action': ParamAction, 'nargs': "+",
                 'dest': 'params', 'help': 'Parameters passed to the orchestration'},
                {'argument': '--no-wait', 'dest': 'background', 'action': 'store_true'},
                orch_run],
    },
    'action': {
        'list': [{'argument': '--version', 'action': 'store', 'type': int,
                  'completer': action_ver_completer},
                 [{'argument': '--json', 'action': 'store_true'},
                  {'argument': '--table', 'action': 'store_true'}],
                 [{'argument': '--like'},
                  {'argument': '--id', 'completer': action_completer},
                  {'argument': '--name', 'completer': action_name_completer}],
                 action_list
                 ],
        'create': [{'argument': 'name'},
                   {'argument': 'action_type', 'choices': [at.name for at in ActionType if at.name != 'NATIVE']},
                   {'argument': '--prompt', 'action': "store_true",
                    'help': 'does not ask for every action parameter one by one'},
                   action_create],
        # 'modify': [{'argument': 'action_template_id', 'completer': action_completer},
        #            action_modify],
        'load': [{'argument': 'file', 'type': argparse.FileType('r')},
                 action_load],
    },
    'exec': {
        'list': [{'argument': '--orch', 'completer': orch_completer},
                 {'argument': '--id', 'dest': 'execution_id'},
                 {'argument': '--server', 'completer': server_completer},
                 {'argument': '--last', 'metavar': 'N', 'type': int, 'help': "shows last N orchestrations"},
                 {'argument': '--asc', 'action': 'store_true'},
                 {'argument': '--detail', 'action': 'store_true'},
                 exec_list]
    },
    'locker': {'show': [{'argument': 'node', 'nargs': '+', 'completer': server_completer}, locker_show],
               'unlock': [{'argument': 'scope', 'choices': [s.name for s in Scope]},
                          {'argument': 'node', 'nargs': '+', 'completer': server_completer},
                          locker_unlock]},
    'software': {
        'add': [{'argument': 'name'},
                {'argument': 'version'},
                {'argument': 'file'},
                {'argument': '--family', 'completer': software_family_completer},
                software_add],
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
    'transfer': {
        'cancel': [{'argument': 'transfer_id'},
                   transfer_cancel],
        'list': [
            {'argument': '--status', 'action': "append", 'nargs': '+', 'choices': [s.name for s in Status]},
            [{'argument': '--id'},
             {'argument': '--last', 'action': 'store', 'type': int}, ],
            transfer_list
        ]},
    'cmd': [{'argument': 'command', 'nargs': '+'},
            {'argument': '--target', 'action': ExtendAction, 'nargs': "+", 'dest': 'hosts',
             'completer': merge_completers([server_completer, granule_completer])},
            {'argument': '--timeout', 'type': int, 'help': 'timeout in seconds to wait for command to terminate'},
            {'argument': '--input'},
            cmd],
    'logfed': {'subscribe': {'log': [{'argument': 'src_server_id',
                                      'metavar': 'source_server_id',
                                      'help': 'source server to get the logs from',
                                      'completer': server_completer},
                                     {'argument': 'target',
                                      'metavar': 'file',
                                      'help': 'log file to watch out'},
                                     {'argument': 'dst_server_id',
                                      'metavar': 'destination_server_id',
                                      'help': 'source server to get the logs from',
                                      'completer': server_completer},
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

    "manager": {"catalog": {"refresh": [manager_catalog_refresh]},
                "locker": {"ignore": [{'argument': 'server_ids', 'metavar': 'NODE', 'nargs': '+',
                                       'completer': server_completer},
                                      functools.partial(manager_locker_ignore, True)],
                           "unignore": [{'argument': 'server_ids', 'metavar': 'NODE', 'nargs': '+',
                                         'completer': server_completer},
                                        functools.partial(manager_locker_ignore, False)]},
                "token": [{'argument': '--raw', 'action': 'store_true'},
                          {'argument': '--expire-time', 'metavar': 'MINUTES',
                           'help': 'Join token expire time in minutes'},
                          token],
                "save": {"login": [manager_save_login]},
                "login": [{'argument': 'username', 'nargs': '?'},
                          manager_login], }
    # "locker": {"lock": [{'argument': "scope", 'choices': ["CATALOG", "ORCHESTRATION", "UPGRADE"]},
    #                     {'argument': "servers", 'nargs': '*', 'completer': server_completer},
    #                     locker_lock],
    #            "unlock": [{'argument': "scope", 'choices': ["CATALOG", "ORCHESTRATION", "UPGRADE"]},
    #                       {'argument': "servers", 'nargs': '*', 'completer': server_completer},
    #                       locker_unlock]},
    ,
    "logging": [{'argument': 'logger', 'completer': logger_completer},
                {'argument': 'level', 'choices': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']},
                logging_cmd],
    "env": {"list": [env_list],
            "get": [{'argument': 'key', 'completer': DshellWordCompleter(environ._environ.keys())},
                    env_get],
            "set": [{'argument': 'key', 'completer': DshellWordCompleter(environ._environ.keys())},
                    {'argument': 'value', 'nargs': '*'},
                    env_set]},
    'exit': [exit_dshell]

}
