from threading import *
from typing import Optional, Callable, Any, Iterable, Mapping

from flask import current_app

from dm.web import db


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
                args = []
                for arg in self._args:
                    if isinstance(arg, db.Model):
                        db.session.expunge(arg)
                        new = db.session.merge(arg, load=False)
                        args.append(new)
                    else:
                        args.append(arg)
                for k, v in self._kwargs:
                    if isinstance(v, db.Model):
                        db.session.expunge(v)
                        new = db.session.merge(v, load=False)
                        self._kwargs.update({k: new})
            super().run()
