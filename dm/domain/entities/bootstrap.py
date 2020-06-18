from dm.domain.entities import Server, Locker, User, ActionTemplate
from dm.web import db


def set_initial(app=None, server=True, user=True, action_template=False):
    if app:
        app.app_context().push()
    db.create_all()
    Locker.set_initial()
    if server:
        Server.set_initial()
    if user:
        User.set_initial()
    if action_template:
        ActionTemplate.set_initial()
    if app:
        app.app_context().pop()
