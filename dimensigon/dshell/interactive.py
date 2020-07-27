import argparse
import inspect
import shlex

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

import dimensigon.dshell.network as ntwrk
from dimensigon.dshell.argparse_raise import create_parser, ArgumentParserRaise
from dimensigon.dshell.commands import nested_dict
from dimensigon.dshell.completer import DshellCompleter
from dimensigon.dshell.helpers import exit_dshell, get_history


def call_func_with_signature(cmd_params):
    func = cmd_params.pop('func')
    sig = inspect.signature(func)
    args = []
    kwargs = {}
    arg_sig = False
    kw_sig = False

    for param in sig.parameters.values():
        if param.kind == param.POSITIONAL_ONLY or (
                param.kind == param.POSITIONAL_OR_KEYWORD and param.default == param.empty):
            args.append(cmd_params.pop(param.name))
        elif param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
            kwargs.update({param.name: cmd_params.pop(param.name, None)})
        elif param.kind == param.VAR_POSITIONAL:
            arg_sig = True
        elif param.kind == param.VAR_KEYWORD:
            kw_sig = True

    if arg_sig and not kw_sig:
        arg_sig = list(cmd_params.values())
        kw_sig = {}
    elif not arg_sig and kw_sig:
        arg_sig = []
        kw_sig = cmd_params
    else:
        arg_sig = []
        kw_sig = {}
    args = args + arg_sig
    func(*args, **{**kwargs, **kw_sig})

def interactive():
    session = PromptSession(completer=DshellCompleter.from_nested_dict(nested_dict),
                            history=get_history('main', InMemoryHistory()),
                            enable_history_search=True, enable_suspend=True)

    parser = ArgumentParserRaise(allow_abbrev=False, prog='')
    parser = create_parser(nested_dict, parser)
    while True:
        try:
            text = session.prompt(f'{ntwrk._username if ntwrk._username else "?"}.dshell> ')
        except KeyboardInterrupt:
            continue  # Control-C pressed. Try again.
        except EOFError:
            exit_dshell()
        try:
            namespace = parser.parse_args(shlex.split(text))
        except (ValueError, argparse.ArgumentError) as e:
            print(e)
            continue
        except SystemExit:
            continue
        else:
            cmd_params = dict(namespace._get_kwargs())

        if 'func' not in cmd_params:
            print(f"No action set for this command: {text}")
        else:
            call_func_with_signature(cmd_params)
