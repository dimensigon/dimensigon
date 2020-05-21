from dm.domain.entities import Server, Locker, User
from dm.web import db


def set_initial(app=None, server=True, user=True):
    if app:
        app.app_context().push()
    db.create_all()
    Locker.set_initial()
    if user:
        User.set_initial()
    if server:
        Server.set_initial()
    if app:
        app.app_context().pop()
