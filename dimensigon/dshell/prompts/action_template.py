import argparse
import json
import os
import shlex
from pprint import pprint

from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.python import PythonLexer
from pygments.lexers.shell import BashLexer
from pygments.lexers.special import TextLexer

import dimensigon.dshell.network as ntwrk
from dimensigon.domain.entities import ActionType
from dimensigon.dshell import validators as v, converters as c
from dimensigon.dshell.argparse_raise import ArgumentParserRaise
from dimensigon.dshell.helpers import get_history, exit_dshell
from dimensigon.dshell.output import dprint
from dimensigon.dshell.prompts.utils import prompt_parameter, code_extension


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
    "action_type": dict(validator=v.Choice([at.name for at in ActionType if at.name != 'NATIVE']),
                        history=InMemoryHistory()),
    "code": dict(edit=code_extension, history=InMemoryHistory(), converter=c.MultiLine),
    "expected_stdout": dict(multiline=True, mouse_support=True, history=InMemoryHistory(), converter=c.MultiLine),
    "expected_stderr": dict(multiline=True, mouse_support=True, history=InMemoryHistory(), converter=c.MultiLine),
    "expected_rc": dict(validator=v.Int, converter=c.Int, history=InMemoryHistory()),
    "schema": dict(edit='.yaml', validator=v.JSON, history=InMemoryHistory(), converter=c.Yaml),
    "system_kwargs": dict(edit='.yaml', validator=v.JSON, history=InMemoryHistory(), converter=c.Yaml),
    "pre_process": dict(edit='.py', history=InMemoryHistory(), converter=c.MultiLine),
    "post_process": dict(edit='.py', history=InMemoryHistory(), converter=c.MultiLine),
}

parser = ArgumentParserRaise(allow_abbrev=False, prog='')
subparser = parser.add_subparsers(dest='cmd')
preview_action = subparser.add_parser('preview')
preview_action.set_defaults(func=lambda x: pprint(x))
set_action = subparser.add_parser('set')
set_action.add_argument('parameter', choices=form.keys())
delete_parser = subparser.add_parser('delete')
delete_parser.add_argument('parameter', choices=form.keys())
submit_action = subparser.add_parser('submit')
dump_action = subparser.add_parser('dump')
dump_action.add_argument('file')
exit_action = subparser.add_parser('exit')

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
            dprint(entity)
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
        elif namespace.cmd == 'submit':
            resp = ntwrk.post(f'api_1_0.{entity_name.replace("_", "")}list', json=entity)
            dprint(resp)
            if resp.ok:
                return
        elif namespace.cmd == 'delete':
            if namespace.parameter not in form.keys():
                dprint("Not a valid parameter. Available: " + ', '.join(form.keys()))
            else:
                entity.pop(namespace.parameter)
                changed = True
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
