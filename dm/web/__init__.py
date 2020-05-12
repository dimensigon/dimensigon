import atexit
import datetime
import json
import os
import threading
import typing as t

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, g, _app_ctx_stack
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from jsonschema import ValidationError
from sqlalchemy import MetaData
from werkzeug.exceptions import HTTPException

from config import config_by_name
from dm.utils.event_handler import EventHandler
from .extensions.flask_executor.executor import Executor
from .helpers import BaseQueryJSON, run_in_background


def scopefunc():
    try:
        return str(id(_app_ctx_stack.top.app)) + str(threading.get_ident())
    except:
        return str(threading.get_ident())


meta = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})


db = SQLAlchemy(query_class=BaseQueryJSON, metadata=meta, session_options=dict(scopefunc=scopefunc))
# db = SQLAlchemy(query_class=BaseQueryJSON)
jwt = JWTManager()
executor = Executor()


class DimensigonApp(Flask):

    def start_background_tasks(self):
        from ..use_cases.log_sender import LogSender
        from dm.web.background_tasks import process_catalog_route_table, process_get_new_version_from_gogs
        if not self.config['TESTING'] or os.getenv('WERKZEUG_RUN_MAIN') == 'true':
            if self.extensions.get('scheduler') is None:
                bs = BackgroundScheduler()
                self.extensions['scheduler'] = bs
                ls = LogSender()
                self.extensions['log_sender'] = ls
                bs.start()

                if self.config.get('AUTOUPGRADE'):
                    bs.add_job(func=process_get_new_version_from_gogs, args=(self,), trigger="interval", hours=6)
                bs.add_job(func=process_catalog_route_table, name="catalog & route upgrade", args=(self,),
                           trigger="interval", minutes=2,
                           next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=5))
                bs.add_job(func=run_in_background, name="log_sender", args=(ls.send_new_data, self),
                           trigger="interval",
                           minutes=2, next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=30))

                # Shut down the scheduler when exiting the app
                atexit.register(lambda: bs.shutdown())

    def run(self, host=None, port=None, debug=None, load_dotenv=True, **options):
        from ..domain.entities import Locker
        Locker.set_initial()
        db.session.commit()
        self.start_background_tasks()
        super(DimensigonApp, self).run(host=host, port=port, debug=debug, load_dotenv=load_dotenv, **options)


def create_app(config_name):
    app = DimensigonApp('dm')
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
    executor.init_app(app)
    app.events = EventHandler()

    app.before_first_request_funcs = [app.start_background_tasks]
    app.before_request(load_global_data_into_context)

    app.register_error_handler(ValidationError, validation_error)
    app.register_error_handler(HTTPException, internal_server_error)

    # API version 0
    from dm.web.routes import root_bp
    from dm.web.api_1_0 import api_bp as api_1_0_bp
    app.register_blueprint(root_bp)
    app.register_blueprint(api_1_0_bp)

    return app


def validation_error(e: ValidationError):
    return {"error": e.message, 'schema': e.schema}, 400


def internal_server_error(e: HTTPException):
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "error": e.description,
    })
    response.content_type = "application/json"
    return response


def load_global_data_into_context():
    from dm.domain.entities import Server, Dimension
    g.server = Server.get_current()
    g.dimension = Dimension.get_current()
