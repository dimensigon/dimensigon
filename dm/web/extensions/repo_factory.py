import inspect
import sys
import typing as t

import dm.framework.utils.dependency_injection as di
# noinspection PyUnresolvedReferences
import dm.repositories
from dm.domain.schemas import set_container
from dm.framework.data.dao import InMemoryDao
from dm.framework.data.dao.db import DbDao
from dm.framework.domain import Repository
from dm.framework.interfaces.dao import IDao
from dm.framework.interfaces.repository import IRepository
from flask import _app_ctx_stack, current_app

from flask import Flask

_app_container = {}


class Repo:

    def __init__(self, app=None):
        self._repo_classes = {name: cls for name, cls in
                             inspect.getmembers(sys.modules['dm.repositories']) if
                             inspect.isclass(cls) and issubclass(cls, Repository) and
                             getattr(cls, 'schema', None) and getattr(cls.schema, '__entity__', None)}
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initializes your repo settings from the application settings.

        :param app: Flask application instance
        """
        # app.teardown_appcontext(self.teardown)

    def create_repos(self, container):
        from dm.web import db
        app = self.get_app()
        initial_content = app.config.get('DM_DATABASE_CONTENT') or {}
        try:
            engine = db.engine
        except AttributeError:
            engine = None
        for name, cls in self._repo_classes.items():
            container.register_by_interface(interface=IDao, constructor=DbDao if engine else InMemoryDao,
                                            qualifier=cls.schema.__entity__,
                                            kwargs={'db': db} if engine else {
                                                'initial_content': initial_content.get(name)}). \
                register_by_interface(interface=IRepository, constructor=cls,
                                      qualifier=cls.schema.__entity__)

        set_container(container)

        _app_container.update({app: container})

    def get_app(self, reference_app=None):
        """Helper method that implements the logic to look up an
        application."""

        if reference_app is not None:
            return reference_app

        if current_app:
            return current_app._get_current_object()

        if self.app is not None:
            return self.app

        raise RuntimeError(
            'No application found. Either work inside a view function or push'
            ' an application context.'
        )

    @property
    def container(self):
        app = self.get_app()
        if app in _app_container:
            return _app_container[app]

    def __getattr__(self, attr) -> IRepository:
        if attr not in self._repo_classes:
            raise AttributeError(f"Repo '{attr}' does not exist")
        return self.container.find_by_interface(interface=IRepository,
                                                qualifier=self._repo_classes.get(attr).schema.__entity__)

    def __iter__(self):
        for cls in self._repo_classes.values():
            yield self.container.find_by_interface(interface=IRepository, qualifier=cls.schema.__entity__)
