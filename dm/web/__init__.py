import atexit
import threading
import typing as t

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, g, _app_ctx_stack
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

from config import config_by_name
from .helpers import BaseQueryJSON


def scopefunc():
    try:
        return str(id(_app_ctx_stack.top.app)) + str(threading.get_ident())
    except:
        return str(threading.get_ident())


db = SQLAlchemy(query_class=BaseQueryJSON, session_options=dict(scopefunc=scopefunc))
# db = SQLAlchemy(query_class=BaseQueryJSON)
jwt = JWTManager()


def create_app(config_name):
    app = Flask('dm')
    if isinstance(config_name, t.Mapping):
        app.config.from_mapping(config_name)
    elif config_name in config_by_name:
        app.config.from_object(config_by_name[config_name])
        config_by_name[config_name].init_app(app)
    else:
        app.config.from_object(config_name)
        if hasattr(config_name, 'init_app'):
            config_name.init_app(app)

    # EXTENSIONS
    db.init_app(app)
    jwt.init_app(app)

    if app.config.get('AUTOUPGRADE'):
        app.scheduler = BackgroundScheduler()
        from ..use_cases.background_tasks import check_new_versions, check_catalog
        app.scheduler.start()
        app.scheduler.add_job(func=check_new_versions, args=(app,), trigger="interval", minutes=2)
        app.scheduler.add_job(func=check_catalog, args=(app,), trigger="interval", minutes=2)

        # Shut down the scheduler when exiting the app
        atexit.register(lambda: app.scheduler.shutdown())

    app.before_request(load_global_data_into_context)

    # API version 0
    from dm.web.routes import root_bp
    from dm.web.api_1_0 import api_bp as api_1_0_bp
    app.register_blueprint(root_bp)
    app.register_blueprint(api_1_0_bp)

    return app


def load_global_data_into_context():
    from dm.domain.entities import Server, Dimension
    g.server = Server.get_current()
    g.dimension = Dimension.get_current()
