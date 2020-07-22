import argparse as argparse
import json
import uuid
from pprint import pprint

import pygments
import requests
from prompt_toolkit import print_formatted_text
from prompt_toolkit.completion import merge_completers
from prompt_toolkit.formatted_text import PygmentsTokens
from pygments.lexers.web import JSONLexer

from dm import defaults
from dm.domain.entities import ActionType
from dm.dshell import environ
from dm.dshell.completer import *
from dm.dshell.helpers import name2id
from dm.dshell.prompts.action_template import subprompt as action_prompt
from dm.dshell.prompts.orchestration import subprompt as orch_prompt
from dm.dshell.utils import clean_none
from dm.utils.helpers import get_now


def status(node):
    for node_id in node:
        try:
            uuid.UUID(node_id)
        except Exception:
            node_id = name2id('api_1_0.serverlist', node_id)
        resp = ntwrk.get('root.healthcheck', headers={'D-Destination': node_id})
        pprint(resp.msg if resp.code else str(resp.exception))


def ping(node):
    for node_id in node:
        try:
            uuid.UUID(node_id)
        except Exception:
            node_id = name2id('api_1_0.serverlist', node_id)
        resp = ntwrk.post('root.ping', headers={'D-Destination': node_id},
                          json={'start_time': get_now().strftime(defaults.DATETIME_FORMAT)})
        pprint(resp.msg if resp.code else str(resp.exception))


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
        pprint(filtered_data)
    else:
        pprint(resp.msg if resp.code else str(resp.exception) if str(
            resp.exception) else resp.exception.__class__.__name__)


def orch_list(**params):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    view_data = dict()
    if params.get('id', None):
        view_data.update({'filter[id]': params['id']})
    if params.get('name'):
        view_data.update({'filter[name]': params['name']})
    if params.get('version', None):
        view_data.update({'filter[version]': params['version']})
    if params.get('details', None):
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
        pprint(filtered_data)
    else:
        pprint(resp.msg if resp.code else str(resp.exception) if str(
            resp.exception) else resp.exception.__class__.__name__)


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
    if resp.code is not None:
        pprint(resp.msg)
    else:
        pprint(str(resp.exception))


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
        tokens = list(pygments.lex(json.dumps(filtered_data[:last or len(filtered_data)], indent=2), lexer=JSONLexer()))
        print_formatted_text(PygmentsTokens(tokens))
    else:
        pprint(resp.msg if resp.code else str(resp.exception) if str(
            resp.exception) else resp.exception.__class__.__name__)


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
    if resp.code == 200:
        pprint(resp.msg)
    else:
        pprint(resp.msg if resp.code is not None else str(resp.exception) if str(
            resp.exception) else resp.exception.__class__.__name__)


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
    pprint(resp.msg if resp.code is not None else str(resp.exception) if str(
        resp.exception) else resp.exception.__class__.__name__)


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
        pprint(filtered_data)
    else:
        pprint(resp.msg if resp.code else str(resp.exception) if str(
            resp.exception) else resp.exception.__class__.__name__)


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
        pprint(filtered_data)
    else:
        pprint(resp.msg if resp.code else str(resp.exception) if str(
            resp.exception) else resp.exception.__class__.__name__)


def transfer_cancel(transfer_id):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    data = {'status': 'CANCELED'}
    resp = ntwrk.patch('api_1_0.transferresource', view_data={'transfer_id': transfer_id}, json=data, **kwargs)
    pprint(resp.msg if resp.code else str(resp.exception) if str(
        resp.exception) else resp.exception.__class__.__name__)


def exec_list(orch=None, server=None, last=None, asc=None, detail=None):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    view_data = dict()
    view = 'api_1_0.orchexecutionlist'

    if orch:
        view_data.update({'filter[orchestration_id]': orch})

    if server:
        view_data.update({'filter[server_id]': server})

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
        tokens = list(pygments.lex(json.dumps(data[:last or len(data)], indent=2), lexer=JSONLexer()))
        print_formatted_text(PygmentsTokens(tokens))
    else:
        pprint(resp.msg if resp.code else str(resp.exception) if str(
            resp.exception) else resp.exception.__class__.__name__)


def cmd(command, hosts, timeout=None, input=None):
    if isinstance(command, list):
        command = ' '.join(command)

    data = {'command': command, 'hosts': hosts}
    if timeout:
        data.update(timeout=timeout)
    if input:
        data.update(input=input.replace('\\n', '\n').replace('\\t', '\t'))
    resp = ntwrk.post('api_1_0.launch_command', view_data={'params': 'human'}, json=data)
    if resp.code:
        tokens = list(pygments.lex(json.dumps(resp.msg, indent=2), lexer=JSONLexer()))
        print_formatted_text(PygmentsTokens(tokens))
    else:
        pprint(str(resp.exception))


def logfed_list():
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    resp = ntwrk.get('api_1_0.loglist', view_data={'params': 'human'}, **kwargs)
    pprint(resp.msg if resp.code else str(resp.exception) if str(
        resp.exception) else resp.exception.__class__.__name__)


def logfed_subscribe(src_server_id, target, dest_server_id, include=None, exclude=None, dest_folder=None,
                     recursive=None, mode=None):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    json_data = dict(src_server_id=src_server_id, target=target, dest_server_id=dest_server_id, include=include,
                     exclude=exclude, dest_folder=dest_folder, recursive=recursive, mode=mode)
    json_data = clean_none(json_data)
    resp = ntwrk.post('api_1_0.loglist', json=json_data, **kwargs)
    pprint(resp.msg if resp.code else str(resp.exception) if str(
        resp.exception) else resp.exception.__class__.__name__)


def logfed_unsubscribe(log_id):
    kwargs = dict(verify=environ.get('SSL_VERIFY'))
    resp = ntwrk.delete('api_1_0.logresource', {'log_id': log_id}, **kwargs)
    if resp.code is not None and resp.msg or resp.exception is not None:
        pprint(resp.msg if resp.code else str(resp.exception) if str(
            resp.exception) else resp.exception.__class__.__name__)


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

def login(username=None, password=None):
    try:
        ntwrk.login(username, password)
    except requests.exceptions.ConnectionError as e:
        print(f"Unable to contact with {environ.get('SCHEME')}://{environ.get('SERVER')}:{environ.get('PORT')}/")
    except Exception as e:
        pprint(e)


def logging_cmd(logger, level):
    logger = logging.getLogger(logger)
    if logger:
        logger.setLevel(level)
    else:
        print(f"Logger '{logger}' does not exist")


def env_list():
    for k, v in environ._environ.items():
        pprint(f"{k}={v}")


def env_get(key):
    pprint(f"{environ.get(key, None)}")


def env_set(key, value):
    environ.set(key, value)


nested_dict = {
    'status': [{'argument': 'node', 'nargs': '+', 'completer': server_completer}, status],
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
    },
    'orch': {
        'list': [{'argument': '--version', 'action': 'store', 'type': int,
                  'completer': orch_ver_completer},
                 {'argument': '--details', 'action': 'store_true'},
                 [{'argument': '--json', 'action': 'store_true'},
                  {'argument': '--table', 'action': 'store_true'}],
                 [{'argument': '--like'},
                  {'argument': '--id', 'completer': orch_completer},
                  {'argument': '--name', 'completer': orch_name_completer}],
                 orch_list
                 ],
        'create': [{'argument': 'name'},
                   {'argument': '--prompt', 'action': "store_true",
                    'help': 'does not ask for every orch parameter one by one'},
                   orch_create],
        'copy': [{'argument': 'orchestration_id', 'completer': orch_completer},
                 orch_copy],
        'load': [{'argument': 'file', 'type': argparse.FileType('r')},
                 orch_load],
        'run': [{'argument': 'orchestration_id', 'completer': orch_completer},
                {'argument': '--target', 'action': DictAction, 'nargs': "+", 'dest': 'hosts',
                 'completer': merge_completers([server_completer, granule_completer])},
                {'argument': '--param', 'action': ParamAction, 'nargs': "+", 'dest': 'params', 'default': {}},
                {'argument': '--foreground', 'dest': 'background', 'action': 'store_false'},
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
                   {'argument': 'version', 'type': int},
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
                 {'argument': '--server', 'completer': server_completer},
                 {'argument': '--last', 'type': int},
                 {'argument': '--asc', 'action': 'store_true'},
                 {'argument': '--detail', 'action': 'store_true'},
                 exec_list]
    },
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
            {'argument': '--status', 'action': "extend", 'nargs': '+',
             'choices': ['WAITING_CHUNKS', 'IN_PROGRESS', 'COMPLETED', 'CHECKSUM_ERROR', 'SIZE_ERROR',
                         'CANCELED']},
            [{'argument': '--id'},
             {'argument': '--last', 'action': 'store', 'type': int}, ],
            transfer_list
        ]},
    'cmd': [{'argument': 'command', 'nargs': '+'},
            {'argument': '--target', 'action': 'extend', 'nargs': "+", 'dest': 'hosts',
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
    # "locker": {"lock": [{'argument': "scope", 'choices': ["CATALOG", "ORCHESTRATION", "UPGRADE"]},
    #                     {'argument': "servers", 'nargs': '*', 'completer': server_completer},
    #                     locker_lock],
    #            "unlock": [{'argument': "scope", 'choices': ["CATALOG", "ORCHESTRATION", "UPGRADE"]},
    #                       {'argument': "servers", 'nargs': '*', 'completer': server_completer},
    #                       locker_unlock]},
    "login": [{'argument': 'username', 'nargs': '?'},
              login],
    "logging": [{'argument': 'logger', 'completer': logger_completer},
                {'argument': 'level', 'choices': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']},
                logging_cmd],
    "env": {"list": [env_list],
            "get": [{'argument': 'key', 'completer': DshellWordCompleter(environ._environ.keys())},
                    env_get],
            "set": [{'argument': 'key', 'completer': DshellWordCompleter(environ._environ.keys())},
                    {'argument': 'value'},
                    env_set]}

}
