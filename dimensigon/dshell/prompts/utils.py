import inspect

import click
from prompt_toolkit import prompt

from dimensigon.dshell.converters import Converter


def prompt_continuation(width, line_number, is_soft_wrap):
    if width >= 2:
        return '.' * (width - 2) + '> '
    elif width == 1:
        return '>'
    else:
        return ''


def code_extension(action_type):
    if action_type == 'SHELL':
        lexer = '.sh'
    elif action_type == 'PYTHON':
        lexer = '.py'
    else:
        lexer = '.txt'
    return lexer


def resolve_callables(kwargs, params):
    prompt_kwargs = dict(kwargs)
    for kk, vv in kwargs.items():
        if callable(vv) and kk not in ('prompt_continuation'):
            sig = inspect.signature(vv)
            callable_kwargs = {kw: params.get(kw, None) for kw in sig.parameters.keys()}
            prompt_kwargs[kk] = vv(**callable_kwargs)
    return prompt_kwargs


def set_parameter(parameter, text, entity, converter: Converter = None):
    if text == '':
        text = None
    elif text == "''" or text == '""':
        text = ""
    else:
        if converter:
            text = converter.load(text)
    if text != entity.get(parameter, None):
        entity[parameter] = text
        return True
    else:
        return False


def prompt_parameter(parameter, entity, form, parent_prompt) -> bool:
    prompt_kwargs = resolve_callables(form[parameter], entity)

    edit = prompt_kwargs.pop('edit', None)
    value = entity.get(parameter, '')
    if 'converter' in prompt_kwargs:
        converter = prompt_kwargs.pop('converter')
        value = converter.dump(value)
    else:
        converter = None
        value = str(value) if value is not None else ''

    if edit:
        text = click.edit(value, extension=edit)
        if text is None:
            text = value
    else:
        text = prompt(
            f"{parent_prompt}.{parameter}>{'>' if prompt_kwargs.get('multiline', False) else ''} ",
            default=value,
            **prompt_kwargs)
    return set_parameter(parameter, text, entity, converter)
