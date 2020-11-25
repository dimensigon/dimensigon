# noinspection PyUnresolvedReferences
from typing import Iterable

from flask import current_app


class ContextApp:
    __slots__ = ['_constructor', '_args', '_kwargs', '_app_container', 'app']

    def __init__(self, constructor, args=None, kwargs=None, app=None):
        self._constructor = constructor
        self._args = args or ()
        self._kwargs = kwargs or {}
        self._app_container = {}
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._app_container.update({app: self._constructor(*self._args, **self._kwargs)})
        app.extensions[self._constructor.__name__.lower()] = self._app_container[app]

    def get_app(self, reference_app=None):
        """Helper method that implements the logic to look up an
        application."""

        if reference_app is not None:
            return reference_app

        if current_app:
            return current_app._get_current_object()

        if self.app:
            return self.app

        raise RuntimeError(
            'No application found. Either work inside a view function or push'
            ' an application context.'
        )

    @property
    def current(self):
        app = self.get_app()
        return self._app_container[app]
