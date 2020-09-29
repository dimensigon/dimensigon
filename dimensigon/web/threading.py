import collections
from threading import *
from typing import Optional, Callable, Any, Iterable, Mapping

from flask import current_app


def merge_iter(arg, c=None):
    from dimensigon.web import db
    c = c or {}
    if id(arg) in c:
        return c[id(arg)]
    elif isinstance(arg, db.Model):
        c.update({id(arg): db.session.merge(arg, load=False)})
        return c[id(arg)]
    elif isinstance(arg, tuple):
        t = tuple(merge_iter(item, c) for item in arg)
    elif isinstance(arg, list):
        for i in range(len(arg)):
            arg[i] = merge_iter(arg[i], c)
        return arg
    elif isinstance(arg, collections.MutableMapping):
        new_map = arg.__class__()
        for k, v in arg:
            new_map[merge_iter(k, c)] = merge_iter(v, c)
        return new_map
    else:
        return arg


class FlaskThread(Thread):
    def __init__(self, group: None = ..., target: Optional[Callable[..., Any]] = ..., name: Optional[str] = ...,
                 args: Iterable[Any] = ..., kwargs: Mapping[str, Any] = ..., *, daemon: Optional[bool] = ...,
                 reattach=True) -> None:
        self.app = current_app._get_current_object()
        self.reattach = reattach
        if daemon is None:
            daemon = True
        super().__init__(group, target, name, args, kwargs, daemon=daemon)

    def run(self) -> None:
        with self.app.app_context():
            if self.reattach:
                self._args = merge_iter(self._args)
                self._kwargs = merge_iter(self._kwargs)
            super().run()
