import argparse
import copy
import os
import shlex
from pprint import pprint

from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import merge_completers
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.python import PythonLexer

import dimensigon.dshell.network as ntwrk
from dimensigon.domain.entities import ActionType
from dimensigon.dshell.argparse_raise import ArgumentParserRaise
from dimensigon.dshell.completer import granule_completer, server_name_completer, action_completer
from dimensigon.dshell.helpers import get_history, exit_dshell
from dimensigon.dshell.prompts.action_template import code_lexer
from dimensigon.dshell.prompts.utils import prompt_parameter
from dimensigon.dshell.validators import ChoiceValidator, IntValidator, JSONValidator, BoolValidator, ListValidator

form = {
    "undo": dict(history=InMemoryHistory()),
    "action_template_id": dict(history=InMemoryHistory(), completer=action_completer),
    "stop_on_error": dict(validator=BoolValidator, history=InMemoryHistory()),
    "stop_undo_on_error": dict(validator=BoolValidator, history=InMemoryHistory()),
    "undo_on_error": dict(validator=BoolValidator, history=InMemoryHistory()),
    "action_type": dict(validator=ChoiceValidator([at.name for at in ActionType if at.name != 'NATIVE']),
                        history=InMemoryHistory()),
    "code": dict(multiline=True, lexer=code_lexer, history=InMemoryHistory()),
    "expected_stdout": dict(multiline=True, history=InMemoryHistory()),
    "expected_stderr": dict(multiline=True, history=InMemoryHistory()),
    "expected_rc": dict(validator=IntValidator(), history=InMemoryHistory()),
    "parameters": dict(multiline=True, lexer=PygmentsLexer(PythonLexer), validator=JSONValidator(),
                       history=InMemoryHistory()),
    "system_kwargs": dict(multiline=True, lexer=PygmentsLexer(PythonLexer), validator=JSONValidator(),
                          history=InMemoryHistory()),
    "pre_process": dict(multiline=True, lexer=PygmentsLexer(PythonLexer), history=InMemoryHistory()),
    "post_process": dict(multiline=True, lexer=PygmentsLexer(PythonLexer), history=InMemoryHistory()),
    "target": dict(completer=merge_completers([granule_completer, server_name_completer]), history=InMemoryHistory()),
    "parent_step_ids": dict(validator=ListValidator())
}

parser = ArgumentParserRaise(allow_abbrev=False, prog='')
subparser = parser.add_subparsers(dest='cmd')
preview_parser = subparser.add_parser('preview')
subpreview_parser = preview_parser.add_subparsers(dest='subcmd')
subpreview_parser.add_parser('action')
set_parser = subparser.add_parser('set')
set_parser.add_argument('parameter', help="Available: " + ', '.join(form.keys()))
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
            print(e)
            continue
        except SystemExit:
            continue

        if namespace.cmd == 'preview':
            if namespace.subcmd == 'action':
                if entity.get('action_template_id', None):
                    resp = ntwrk.get('api_1_0.actiontemplateresource', view_data={'action_template_id': entity['action_template_id']})
                    if resp.ok:
                        pprint(resp.msg)
                    else:
                        if resp.code is not None:
                            pprint(resp.msg)
                        else:
                            print(str(resp.exception))
                else:
                    print('no action_template_id set')
            elif namespace.subcmd is None:
                pprint(entity, indent=4)
        elif namespace.cmd == 'set':
            if namespace.parameter not in form.keys():
                print("Not a valid parameter. Available: " + ', '.join(form.keys()))
            else:
                try:
                    if prompt_parameter(namespace.parameter, entity, form, f"{parent_prompt}:{entity['id']}"):
                        changed = True
                except KeyboardInterrupt:
                    continue  # Control-C pressed. Try again.
                except EOFError:
                    exit_dshell(rc=1)
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
