import concurrent
import os
import shlex

from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory

from dimensigon.dshell import network as ntwrk
from dimensigon.dshell import validators as v, converters as c
from dimensigon.dshell.argparse_raise import ArgumentParserRaise
from dimensigon.dshell.completer import server_completer
from dimensigon.dshell.helpers import get_history
from dimensigon.dshell.output import dprint
from dimensigon.dshell.prompts.utils import prompt_parameter

form = {
    "target": dict(history=InMemoryHistory(), completer=server_completer, validator=v.List(), converter=c.List()),
    "timeout": dict(history=InMemoryHistory(), validator=v.Int(), converter=c.Int()),
    "input": dict(history=InMemoryHistory()),
}

parser = ArgumentParserRaise(allow_abbrev=False, prog='')
subparser = parser.add_subparsers(dest='cmd')
target_parser = subparser.add_parser('target')
target_parser.add_argument('servers')
run_parser = subparser.add_parser('run')
exit_action = subparser.add_parser('exit')

history = None

entity_name = os.path.basename(__file__).rstrip('.py')

ids = []
name2id = {}


def fill_data():
    global ids, name2id
    resp = ntwrk.get('api_1_0.serverlist', timeout=15)
    if resp.ok:
        ids = []
        name2id = {}
        for s in resp.msg:
            name2id[s.get('name')] = s.get('id')
            ids.append(s.get('id'))
    else:
        return resp


def execute_cmd(command: str, target, timeout=None, input=None):
    global name2id, ids
    data = {'command': command, 'target': target}
    if timeout:
        data.update(timeout=timeout)
    if input:
        data.update(input=input.replace('\\n', '\n').replace('\\t', '\t'))
    if target in name2id:
        dest = name2id[target]
    elif target in ids:
        dest = target
    else:
        raise ValueError(f'invalid target {target}')
    resp = ntwrk.post('api_1_0.launch_command', view_data={'params': 'human'}, json=data,
                      headers={'D-Destination': dest})
    return resp


def subprompt(entity, changed=False, ask_all=False, parent_prompt=None):
    global history, ids, name2id

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        if history is None:
            history = get_history(entity_name, InMemoryHistory())

        if ask_all:
            for k, v in form.items():
                try:
                    if prompt_parameter(k, entity, form,
                                        parent_prompt=f"{parent_prompt} {entity_name}"):
                        changed = True
                except KeyboardInterrupt:
                    entity[k] = None
                except EOFError:
                    break

        while True:
            try:
                text = prompt(f"{parent_prompt} {entity_name}> ", history=history,
                              auto_suggest=AutoSuggestFromHistory())
            except KeyboardInterrupt:
                continue
            except EOFError:
                return

            splitted = shlex.split(text)
            if not splitted:
                continue
            if splitted[0] == 'target':
                if splitted[1:]:
                    resp = fill_data()
                    if resp:
                        dprint(resp)
                        continue
                    unknown = [s for s in splitted[1:] if s not in name2id and s not in ids]
                    if unknown:
                        dprint(f"Unknown target {', '.join(unknown)}")
                    else:
                        entity['target'] = splitted[1:]
                else:
                    dprint(' '.join(entity['target']))
            elif splitted[0] == 'set':
                if len(splitted[1:]) == 1 and splitted[1] in form:
                    try:
                        if prompt_parameter(splitted[1], entity, form,
                                            f"{parent_prompt}{entity_name}"):
                            changed = True
                    except KeyboardInterrupt:
                        continue  # Control-C pressed. Try again.
                    except EOFError:
                        return
                else:
                    dprint("Not a valid parameter. Available: " + ', '.join(form.keys()))

            elif splitted[0] == 'exit':
                return
            else:
                resp = fill_data()
                if resp:
                    dprint(resp)
                    continue
                if entity['target']:
                    first = True
                    future_to_server = {
                        executor.submit(execute_cmd, text, server, timeout=entity.get('timeout'),
                                        input=entity.get('input')): server for server in
                        entity['target']}
                    for future in concurrent.futures.as_completed(future_to_server):
                        server = future_to_server[future]
                        try:
                            resp = future.result()
                        except Exception as exc:
                            dprint(exc)
                        else:
                            if first:
                                if "cmd" in resp.msg:
                                    resp.msg.pop('cmd')
                                if "input" in resp.msg:
                                    input = resp.msg.pop('input')
                                    if input:
                                        dprint(f"input: {input}")
                                first = False
                            else:
                                resp.msg.pop('cmd', None)
                                resp.msg.pop('input', None)
                            dprint(resp)
                else:
                    dprint("no target specified")
