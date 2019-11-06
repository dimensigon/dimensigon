import datetime
import functools
import inspect

from dm.framework.domain import fields
from dm.framework.domain.schema import Schema

FIELD = 'data_mark'


def data_mark(_cls_or_func=None, *args, **kwargs):
    """Returns the same class as was passed in, with data_mark field passed
    """

    def wrap(cls_or_func):
        if inspect.isclass(cls_or_func) and issubclass(cls_or_func, Schema):
            cls_or_func._declared_fields.update(
                {FIELD: fields.DateTime(default=datetime.datetime.now(), format='%Y%m%d%H%M%S%f')})
            return cls_or_func
        elif inspect.isfunction(cls_or_func):
            @functools.wraps(cls_or_func)
            def wrapper(*args, **kwargs):
                if FIELD in kwargs:
                    setattr(args[0], FIELD, kwargs.pop(FIELD))
                else:
                    setattr(args[0], FIELD, None)
                return cls_or_func(*args, **kwargs)

            return wrapper
        else:
            return cls_or_func

    # See if we're being called as @data_mark or @data_mark().
    if _cls_or_func is None:
        # We're called with parens.
        return wrap
    else:
        # We're called as @data_mark without parens.
        return wrap(_cls_or_func)
