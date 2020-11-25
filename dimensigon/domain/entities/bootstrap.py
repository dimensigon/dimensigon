from contextlib import contextmanager

from flask import has_app_context, current_app

from dimensigon.domain.entities import Server, Locker, User, ActionTemplate
from dimensigon.web import db


@contextmanager
def prepare_context(app=None):
    ctx = None
    if app:
        ctx = app.app_context()
        ctx.push()

    if not has_app_context():
        ctx = current_app.app_context()
        ctx.push()

    yield ctx

    if ctx:
        ctx.pop()


def _bootstrap_database():
    db.create_all()


def set_initial(app=None, session=None, server=True, user=True, action_template=False):
    """Used for generate database on testing"""
    with prepare_context(app) as ctx:
        _bootstrap_database()
        Locker.set_initial()
        if server:
            Server.set_initial()
        if user:
            User.set_initial()
        if action_template:
            ActionTemplate.set_initial()

        if ctx:
            db.session.commit()
