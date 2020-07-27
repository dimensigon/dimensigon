import atexit
import datetime
import os
import threading
import typing as t

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, g, _app_ctx_stack, _request_ctx_stack
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

from dimensigon.utils.event_handler import EventHandler
from dimensigon.web import errors
from dimensigon.web.config import config_by_name
from .extensions.flask_executor.executor import Executor
from .helpers import BaseQueryJSON, run_in_background
from ..utils.helpers import get_now


def scopefunc():
    try:
        return str(id(_app_ctx_stack.top.app)) + str(threading.get_ident()) + str(id(_request_ctx_stack.top.request))
    except:
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


class DimensigonFlask(Flask):

    def start_background_tasks(self):
        from ..use_cases.log_sender import LogSender
        from dimensigon.web.background_tasks import process_catalog_route_table, process_get_new_version_from_gogs
        if not self.config['TESTING'] or os.getenv('WERKZEUG_RUN_MAIN') == 'true':
            if self.extensions.get('scheduler') is None and self.config['SCHEDULER']:
                bs = BackgroundScheduler()
                self.extensions['scheduler'] = bs
                ls = LogSender()
                self.extensions['log_sender'] = ls
                bs.start()

                if self.config.get('AUTOUPGRADE'):
                    bs.add_job(func=process_get_new_version_from_gogs, args=(self,), trigger="interval", hours=6)
                bs.add_job(func=process_catalog_route_table, name="catalog & route upgrade", args=(self,),
                           trigger="interval", minutes=5,
                           next_run_time=get_now() + datetime.timedelta(seconds=5))
                bs.add_job(func=run_in_background, name="log_sender", args=(ls.send_new_data, self),
                           trigger="interval",
                           minutes=2, next_run_time=get_now() + datetime.timedelta(seconds=30))

                # Shut down the scheduler when exiting the app
                atexit.register(lambda: bs.shutdown())

    def run(self, host=None, port=None, debug=None, load_dotenv=True, **options):
        from dimensigon.domain.entities.bootstrap import set_initial
        set_initial(server=False, user=False)
        db.session.commit()
        self.start_background_tasks()
        super(DimensigonFlask, self).run(host=host, port=port, debug=debug, load_dotenv=load_dotenv, **options)


def _initialize_blueprint(app):
    from dimensigon.web.routes import root_bp
    from dimensigon.web.api_1_0 import api_bp as api_1_0_bp

    app.register_blueprint(root_bp)
    handle_exception = app.handle_exception
    handle_user_exception = app.handle_user_exception
    app.register_blueprint(api_1_0_bp)
    app.handle_exception = handle_exception
    app.handle_user_exception = handle_user_exception


def _initialize_errorhandlers(application):
    '''
    Initialize error handlers
    '''
    from dimensigon.web.errors import bp_errors
    application.register_blueprint(bp_errors)


def create_app(config_name):
    app = DimensigonFlask('dimensigon')
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
    _initialize_blueprint(app)
    _initialize_errorhandlers(app)

    return app


@jwt.user_loader_callback_loader
def user_loader_callback(identity):
    from ..domain.entities import User
    return User.query.get(identity)


def load_global_data_into_context():
    from dimensigon.domain.entities import Server, Dimension
    g.server = Server.get_current()
    g.dimension = Dimension.get_current()
