import typing as t
from contextlib import contextmanager

from flask import Flask, g
from flask_jwt_extended import JWTManager
from sqlalchemy.orm import sessionmaker

from config import config_by_name
from dm import db
from .helpers import BaseQueryJSON

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

    # EXTENSIONS
    @app.teardown_appcontext
    def cleanup(resp_or_exc):
        db.session.remove()

    jwt.init_app(app)

    # TODO: check ssl redirection and Talisman library
    # if app.config['SSL_REDIRECT']:
    #     from flask_talisman import Talisman
    #     talisman = Talisman(app)

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


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    # configure Session class with desired options
    Session = sessionmaker()

    # associate it with our custom Session class
    Session.configure(bind=db.engine)

    # work with the session
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
