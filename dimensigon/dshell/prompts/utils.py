import inspect

from prompt_toolkit import prompt


def resolve_callables(kwargs, params):
    prompt_kwargs = dict(kwargs)
    for kk, vv in kwargs.items():
        if callable(vv):
            sig = inspect.signature(vv)
            callable_kwargs = {kw: params.get(kw, None) for kw in sig.parameters.keys()}
            prompt_kwargs[kk] = vv(**callable_kwargs)
    return prompt_kwargs


def prompt_parameter(parameter, entity, form, parent_prompt) -> bool:
    prompt_kwargs = resolve_callables(form[parameter], entity)

    text = prompt(
        f"{parent_prompt}.{parameter}>{'>' if prompt_kwargs.get('multiline', False) else ''} ",
        default=str(entity.get(parameter, '')) if entity.get(parameter, '') != '' else '',
        **prompt_kwargs)
    if text == '':
        text = None
    elif text == "''" or text == '""':
        text = ""
    else:
        if 'validator' in prompt_kwargs and hasattr(prompt_kwargs['validator'], 'transform'):
            text = prompt_kwargs['validator'].transform(text)
    if text != entity.get(parameter, None):
        entity[parameter] = text
        return True
    else:
        return False
