import argparse
import inspect
import shlex

from prompt_toolkit import PromptSession
from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from dimensigon.dshell import environ as env
from dimensigon.dshell.argparse_raise import create_parser, ArgumentParserRaise
from dimensigon.dshell.commands import nested_dict
from dimensigon.dshell.completer import DshellCompleter
from dimensigon.dshell.helpers import exit_dshell, get_history
from dimensigon.dshell.output import dprint
from dimensigon.utils import subprocess


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
    try:
        func(*args, **{**kwargs, **kw_sig})
    except Exception as e:
        dprint(e)


style = Style.from_dict({
    # User input (default text).
    # '':          '#ff0066',

    # Prompt.
    'username': 'green',
    'at': '#884444',
    'host': 'green bold',
    'path': 'ansicyan',
})


def interactive():
    session = PromptSession(completer=DshellCompleter.from_nested_dict(nested_dict),
                            history=get_history('main', InMemoryHistory()), clipboard=PyperclipClipboard(),
                            enable_history_search=True, enable_suspend=True)

    parser = ArgumentParserRaise(allow_abbrev=False, prog='')
    parser = create_parser(nested_dict, parser)
    while True:
        message = [
            ('class:username', env._username if env._username else "?"),
            ('class:at', '@'),
            ('class:host', env.get("SERVER") if env.get("SERVER") else "?"),
            ('', ':'),
            ('class:path', 'dshell'),
            ('', '> '),
        ]
        try:
            text = session.prompt(message, style=style)
        except KeyboardInterrupt:
            continue  # Control-C pressed. Try again.
        except EOFError:
            exit_dshell()

        if text.startswith('!'):
            subprocess.call(text.lstrip('!'), shell=True)
        else:
            try:
                namespace = parser.parse_args(shlex.split(text))
            except (ValueError, argparse.ArgumentError) as e:
                dprint(e)
                continue
            except SystemExit:
                continue
            except Exception as e:
                dprint(e)
                continue
            else:
                cmd_params = vars(namespace)

            if not text:
                continue
            elif text == 'help':
                parser.print_usage()
            elif text and len(cmd_params) == 0:
                try:
                    parser.parse_args(shlex.split(text) + ['-h'])
                except SystemExit:
                    continue
            else:
                call_func_with_signature(cmd_params)
