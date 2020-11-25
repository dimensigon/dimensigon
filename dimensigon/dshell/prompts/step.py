import argparse
import copy
import os
import shlex

from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import merge_completers
from prompt_toolkit.history import InMemoryHistory

import dimensigon.dshell.network as ntwrk
from dimensigon.domain.entities import ActionType
from dimensigon.dshell import validators as v, converters as c
from dimensigon.dshell.argparse_raise import ArgumentParserRaise
from dimensigon.dshell.completer import granule_completer, server_name_completer, action_completer
from dimensigon.dshell.helpers import get_history, exit_dshell
from dimensigon.dshell.output import dprint
from dimensigon.dshell.prompts.utils import prompt_parameter, code_extension

form = {
    "undo": dict(history=InMemoryHistory()),
    "name": dict(history=InMemoryHistory()),
    "action_template_id": dict(history=InMemoryHistory(), completer=action_completer),
    "stop_on_error": dict(validator=v.Bool, converter=c.Bool, history=InMemoryHistory()),
    "stop_undo_on_error": dict(validator=v.Bool, converter=c.Bool, history=InMemoryHistory()),
    "undo_on_error": dict(validator=v.Bool, converter=c.Bool, history=InMemoryHistory()),
    "action_type": dict(validator=v.Choice([at.name for at in ActionType if at.name != 'NATIVE']),
                        history=InMemoryHistory()),
    "code": dict(edit=code_extension, history=InMemoryHistory(), converter=c.MultiLine),
    "expected_stdout": dict(multiline=True, mouse_support=True, history=InMemoryHistory(), converter=c.MultiLine),
    "expected_stderr": dict(multiline=True, mouse_support=True, history=InMemoryHistory(), converter=c.MultiLine),
    "expected_rc": dict(validator=v.Int(), converter=c.Int, history=InMemoryHistory()),
    "schema": dict(edit='.yaml', validator=v.JSON, history=InMemoryHistory(), converter=c.Yaml),
    "system_kwargs": dict(edit='.yaml', validator=v.JSON, history=InMemoryHistory(), converter=c.Yaml),
    "pre_process": dict(edit='.py', history=InMemoryHistory(), converter=c.MultiLine),
    "post_process": dict(edit='.py', history=InMemoryHistory(), converter=c.MultiLine),
    "target": dict(completer=merge_completers([granule_completer, server_name_completer]), history=InMemoryHistory()),
    "parent_step_ids": dict(validator=v.List(','), converter=c.List(','))
}

parser = ArgumentParserRaise(allow_abbrev=False, prog='')
subparser = parser.add_subparsers(dest='cmd')
preview_parser = subparser.add_parser('preview')
subpreview_parser = preview_parser.add_subparsers(dest='subcmd')
subpreview_parser.add_parser('action')
set_parser = subparser.add_parser('set')
set_parser.add_argument('parameter', help=', '.join(form.keys()))
delete_parser = subparser.add_parser('delete')
delete_parser.add_argument('parameter', help=', '.join(form.keys()))
save_parser = subparser.add_parser('save')
exit_parser = subparser.add_parser('exit')

history = None

entity_name = os.path.basename(__file__).split('.py')[0]


def subprompt(entity, changed=False, ask_all=False, parent_prompt=None):
    global history
    if history is None:
        history = get_history(entity_name, InMemoryHistory())

    entity = copy.deepcopy(entity)
    if ask_all:
        for k, v in form.items():
            if k not in entity:
                try:
                    if prompt_parameter(k, entity, form, f"{parent_prompt}:{entity['id']}"):
                        changed = True
                except KeyboardInterrupt:
                    entity[k] = None
                except EOFError:
                    exit_dshell()

    while True:
        try:
            text = prompt(f"{parent_prompt}:{entity['id']}> ", history=history,
                          auto_suggest=AutoSuggestFromHistory())
        except KeyboardInterrupt:
            continue
        except EOFError:
            exit_dshell(rc=1)
        try:
            namespace = parser.parse_args(shlex.split(text))
        except (ValueError, argparse.ArgumentError) as e:
            dprint(e)
            continue
        except SystemExit:
            continue

        if namespace.cmd == 'preview':
            if namespace.subcmd == 'action':
                if entity.get('action_template_id', None):
                    resp = ntwrk.get('api_1_0.actiontemplateresource',
                                     view_data={'action_template_id': entity['action_template_id']})
                    dprint(resp)
                else:
                    dprint('no action_template_id set')
            elif namespace.subcmd is None:
                dprint(entity)
        elif namespace.cmd == 'set':
            if namespace.parameter not in form.keys():
                dprint("Not a valid parameter. Available: " + ', '.join(form.keys()))
            else:
                try:
                    if prompt_parameter(namespace.parameter, entity, form, f"{parent_prompt}:{entity['id']}"):
                        changed = True
                except KeyboardInterrupt:
                    continue  # Control-C pressed. Try again.
                except EOFError:
                    exit_dshell(rc=1)
        elif namespace.cmd == 'delete':
            if namespace.parameter not in form.keys():
                dprint("Not a valid parameter. Available: " + ', '.join(form.keys()))
            else:
                entity.pop(namespace.parameter)
                changed = True
        elif namespace.cmd == 'save':
            if changed:
                return entity
            else:
                return None
        elif namespace.cmd == 'exit':
            if changed:
                text = ''
                while text.lower().strip() not in ('y', 'n'):
                    text = prompt('If you exit you will lose the changes. Do you want to continue? (y/n): ')
                if text.lower().strip() == 'y':
                    break
            else:
                break
