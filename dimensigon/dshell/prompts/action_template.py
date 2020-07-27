import argparse
import json
import os
import shlex
from pprint import pprint

from click import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.python import PythonLexer
from pygments.lexers.shell import BashLexer
from pygments.lexers.special import TextLexer

import dimensigon.dshell.network as ntwrk
from dimensigon.domain.entities import ActionType
from dimensigon.dshell.argparse_raise import ArgumentParserRaise
from dimensigon.dshell.helpers import get_history, exit_dshell
from dimensigon.dshell.prompts.utils import prompt_parameter
from dimensigon.dshell.validators import ChoiceValidator, IntValidator, JSONValidator

parser = ArgumentParserRaise(allow_abbrev=False, prog='')
subparser = parser.add_subparsers(dest='cmd')
preview_action = subparser.add_parser('preview')
preview_action.set_defaults(func=lambda x: pprint(x))
set_action = subparser.add_parser('set')
set_action.add_argument('parameter')
submit_action = subparser.add_parser('submit')
dump_action = subparser.add_parser('dump')
dump_action.add_argument('file')
exit_action = subparser.add_parser('exit')


def code_lexer(action_type):
    if action_type == 'SHELL':
        lexer = PygmentsLexer(BashLexer)
    elif action_type == 'PYTHON':
        lexer = PygmentsLexer(PythonLexer)
    else:
        lexer = PygmentsLexer(TextLexer)
    return lexer


form = {
    "name": dict(history=InMemoryHistory()),
    "version": dict(history=InMemoryHistory()),
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
}

history = None

entity_name = os.path.basename(__file__).rstrip('.py')


def subprompt(entity, changed=False, ask_all=False, parent_prompt=None):
    global history
    if history is None:
        history = get_history(entity_name, InMemoryHistory())

    if ask_all:
        for k, v in form.items():
            if k not in entity:
                try:
                    if prompt_parameter(k, entity, entity_name, form, parent_prompt):
                        changed = True
                except KeyboardInterrupt:
                    entity[k] = None
                except EOFError:
                    exit_dshell()

    while True:
        try:
            text = prompt(f"{parent_prompt}{entity_name}('{entity['name']}')> ", history=history,
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
            pprint(entity)
        elif namespace.cmd == 'set':
            if namespace.parameter not in form.keys():
                print("Not a valid parameter. Available: " + ', '.join(form.keys()))
            else:
                try:
                    if prompt_parameter(namespace.parameter, entity, form, f"{parent_prompt}{entity_name}('{entity['name']}')"):
                        changed = True
                except KeyboardInterrupt:
                    continue  # Control-C pressed. Try again.
                except EOFError:
                    exit_dshell(rc=1)
        elif namespace.cmd == 'submit':
            if 'id' in entity:
                resp = ntwrk.patch(f'api_1_0.{entity_name.replace("_", "")}resource', json=entity)
            else:
                resp = ntwrk.post(f'api_1_0.{entity_name.replace("_", "")}list', json=entity)

            if resp.code and 200 <= resp.code <= 299:
                if resp.msg:
                    pprint(resp.msg)
                break
            else:
                pprint(resp.msg if resp.code is not None else str(resp.exception) if str(
                    resp.exception) else resp.exception.__class__.__name__)
        elif namespace.cmd == 'dump':
            with open(namespace.file, 'w') as dumpfile:
                json.dump(entity, dumpfile, indent=4)
            changed = False
        elif namespace.cmd == 'exit':
            if changed:
                text = ''
                while text.lower().strip() not in ('y', 'n'):
                    text = prompt('If you exit you will lose the changes. Do you want to continue? (y/n): ')
                if text.lower().strip() == 'y':
                    break
            else:
                break
