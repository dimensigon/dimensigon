import inspect

import click
from prompt_toolkit import prompt


def resolve_callables(kwargs, params):
    prompt_kwargs = dict(kwargs)
    for kk, vv in kwargs.items():
        if callable(vv):
            sig = inspect.signature(vv)
            callable_kwargs = {kw: params.get(kw, None) for kw in sig.parameters.keys()}
            prompt_kwargs[kk] = vv(**callable_kwargs)
    return prompt_kwargs


def set_parameter(parameter, text, entity, load=None):
    if text == '':
        text = None
    elif text == "''" or text == '""':
        text = ""
    else:
        if callable(load):
            text = load(text)
    if text != entity.get(parameter, None):
        entity[parameter] = text
        return True
    else:
        return False


def prompt_parameter(parameter, entity, form, parent_prompt) -> bool:
    prompt_kwargs = resolve_callables(form[parameter], entity)

    edit = prompt_kwargs.pop('edit', False)
    value = entity.get(parameter, '')
    if 'validator' in prompt_kwargs and hasattr(prompt_kwargs['validator'], 'load'):
        value = prompt_kwargs['validator'].dump(value)
    else:
        value = str(value) if value is not None else ''

    if edit:
        text = click.edit(str() if value != '' else '')
    else:
        text = prompt(
            f"{parent_prompt}.{parameter}>{'>' if prompt_kwargs.get('multiline', False) else ''} ",
            default=value,
            **prompt_kwargs)
    return set_parameter(parameter, text, entity,
                         prompt_kwargs['validator'].load if 'validator' in prompt_kwargs and hasattr(
                             prompt_kwargs['validator'], 'load') else None)

