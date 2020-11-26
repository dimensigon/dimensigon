import argparse
import copy
import json
import os
import shlex
from pprint import pprint

from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory

import dimensigon.dshell.network as ntwrk
from dimensigon.dshell import validators as v, converters as c
from dimensigon.dshell.argparse_raise import ArgumentParserRaise
from dimensigon.dshell.helpers import get_history, exit_dshell
from dimensigon.dshell.output import dprint
from dimensigon.dshell.prompts.step import subprompt as step_subprompt
from dimensigon.dshell.prompts.utils import prompt_parameter, prompt_continuation

form = {
    "name": dict(history=InMemoryHistory()),
    "description": dict(multiline=True, history=InMemoryHistory(), mouse_support=True,
                        prompt_continuation=prompt_continuation,
                        converter=c.MultiLine),
    "stop_on_error": dict(validator=v.Bool, converter=c.Bool, history=InMemoryHistory()),
    "stop_undo_on_error": dict(validator=v.Bool, converter=c.Bool, history=InMemoryHistory()),
    "undo_on_error": dict(validator=v.Bool, converter=c.Bool, history=InMemoryHistory()),
}

parser = ArgumentParserRaise(allow_abbrev=False, prog='')
subparser = parser.add_subparsers(dest='cmd')
preview_action = subparser.add_parser('preview')
preview_action.set_defaults(func=lambda x: pprint(x))
set_action = subparser.add_parser('set')
set_action.add_argument('parameter', choices=form.keys())
delete_parser = subparser.add_parser('delete')
delete_subparser = delete_parser.add_subparsers(dest='subcmd')
delete_parameter_parser = delete_subparser.add_parser('parameter')
delete_parameter_parser.add_argument('parameter', choices=form.keys())
delete_step_parser = delete_subparser.add_parser('step')
delete_step_parser.add_argument('step_id')
submit_action = subparser.add_parser('submit')
dump_action = subparser.add_parser('dump')
dump_action.add_argument('file')
exit_action = subparser.add_parser('exit')
step_parser = subparser.add_parser('step', help='adds or modifies a step')
step_parser.add_argument('id_or_type', help='modifies a step. To create a new step, specify "do" or "undo" step')

history = None

entity_name = os.path.basename(__file__).rstrip('.py')


def submit(entity):
    resp = ntwrk.post('api_1_0.orchestrations_full', json=entity)
    dprint(resp)
    return resp.ok


def subprompt(entity, changed=False, ask_all=False, parent_prompt=None):
    global history

    if history is None:
        history = get_history(entity_name, InMemoryHistory())

    if ask_all:
        for k, v in form.items():
            if k not in entity:
                try:
                    if prompt_parameter(k, entity, form, f"{parent_prompt}{entity_name}('{entity['name']}')"):
                        changed = True
                except KeyboardInterrupt:
                    entity[k] = None
                except EOFError:
                    pass

    while True:
        try:
            text = prompt(f"{parent_prompt}{entity_name}('{entity['name']}')> ", history=history,
                          auto_suggest=AutoSuggestFromHistory())
        except KeyboardInterrupt:
            continue
        except EOFError:
            return
        try:
            namespace = parser.parse_args(shlex.split(text))
        except (ValueError, argparse.ArgumentError) as e:
            print(e)
            continue
        except SystemExit:
            continue

        if namespace.cmd == 'preview':
            orch = copy.deepcopy(entity)
            for s in orch['steps']:
                s.pop('orchestration_id', None)
            dprint(orch)
        elif namespace.cmd == 'set':
            if namespace.parameter not in form.keys():
                dprint("Not a valid parameter. Available: " + ', '.join(form.keys()))
            else:
                try:
                    if prompt_parameter(namespace.parameter, entity, form,
                                        f"{parent_prompt}{entity_name}('{entity['name']}')"):
                        changed = True
                except KeyboardInterrupt:
                    continue  # Control-C pressed. Try again.
                except EOFError:
                    exit_dshell(rc=1)
        elif namespace.cmd == 'delete':
            if namespace.subcmd == 'step':
                for s in copy.copy(entity['steps']):
                    if s['id'] == namespace.step_id:
                        entity['steps'].remove(s)
                        changed = True
                # delete parent dependencies
                for s in entity['steps']:
                    if namespace.step_id in s['parent_step_ids']:
                        s['parent_step_ids'].remove(namespace.step_id)
                        changed = True
            elif namespace.subcmd == 'parameter':
                if namespace.parameter not in form.keys():
                    dprint("Not a valid parameter. Available: " + ', '.join(form.keys()))
                else:
                    entity.pop(namespace.parameter)
                    changed = True
        elif namespace.cmd == 'submit':
            created = submit(entity)
            if created:
                return
        elif namespace.cmd == 'dump':
            orch = copy.deepcopy(entity)
            for s in orch['steps']:
                s.pop('orchestration_id', None)
            with open(namespace.file, 'w') as dumpfile:
                json.dump(orch, dumpfile, indent=4)
            changed = False
        elif namespace.cmd == 'step':
            if 'steps' not in entity:
                entity['steps'] = []

            step = {}
            if namespace.id_or_type not in ('do', 'undo'):
                for s in entity.get('steps', []):
                    if str(s.get('id')) == namespace.id_or_type:
                        step = s
                        break
                else:
                    dprint('id step does not exists in this orchestration')
                    continue

            if not step:
                # generate id
                step['id'] = str(int(max([s.get('id') for s in entity.get('steps', [])] or [0])) + 1)
                step['undo'] = namespace.id_or_type == 'undo'
                step['parent_step_ids'] = []
            changed_step = step_subprompt(step, parent_prompt=f"{parent_prompt}{entity_name}('{entity['name']}')")
            if changed_step:
                changed = True
                steps = entity.get('steps', [])
                id2step = {s['id']: s for s in steps}
                if changed_step.get('id') in id2step:
                    id2step[changed_step.get('id')].update(**changed_step)
                else:
                    entity['steps'].append(changed_step)

        elif namespace.cmd == 'exit':
            if changed:
                text = ''
                while text.lower().strip() not in ('y', 'n'):
                    text = prompt('If you exit you will lose the changes. Do you want to continue? (y/n): ')
                if text.lower().strip() == 'y':
                    return
            else:
                return
