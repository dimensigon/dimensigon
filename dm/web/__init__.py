import ipaddress
import socket
import typing as t
import uuid
from contextlib import contextmanager

import jsonschema
from flask import Flask, current_app, Response, appcontext_tearing_down, g
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import sessionmaker

import dm.web.exceptions as exc
from config import config_by_name
from dm.utils.async_operator import AsyncOperator
from dm.web.extensions.context_app import ContextApp

PROTOCOL = 'https'
HOSTNAME = socket.gethostname()
IP = ipaddress.ip_address(socket.gethostbyname(HOSTNAME))
DEFAULT_PORT = 24000

db = SQLAlchemy()
migrate = Migrate(db)
jwt = JWTManager()


def create_app(config=None):
    global PROTOCOL
    app = Flask(__name__)
    if isinstance(config, t.Mapping):
        app.config.from_mapping(config)
    elif config in config_by_name:
        app.config.from_object(config_by_name[config])
    else:
        app.config.from_object(config)

    # GLOBAL CONFIG
    # app.logger.addHandler(logging.StreamHandler(sys.stdout))
    # app.logger.setLevel(logging.INFO)

    # AUTHENTICATION CONFIG

    # EXTENSIONS
    db.init_app(app)
    migrate.init_app(app)
    jwt.init_app(app)
    app.queue = AsyncOperator()

    # API version 0
    from dm.web.routes import root_bp
    from dm.web.api_1_0 import api_bp as api_1_0_bp
    app.register_blueprint(root_bp)
    app.register_blueprint(api_1_0_bp)

    return app

def load_global_data_into_context():
    from dm.domain.entities import Server, Dimension
    g.server = Server.query.get(current_app.server_id)
    g.dimension = Dimension.query.get(current_app.dimension_id)


def set_variables():
    from dm.domain.entities import Server, Dimension
    count = Server.query.count()
    server_name = current_app.config.get('SERVER_NAME', None) or HOSTNAME
    port = current_app.config.get('PORT', None) or DEFAULT_PORT
    # TODO: better initialization to avoid problems when changing SERVER_NAME or PORT once initialized
    if count == 0:
        server = Server(name=server_name, port=port, ip=IP)
        db.session.add(server)
        db.session.commit()
    else:
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            raise exc.ServerLookupError(
                f"Server '{server_name}' not found in database. Specify SERVER_NAME=server_or_ip:port")

    current_app.server_id = server.id if server else None

    count = Dimension.query.count()
    dimension = None
    if count == 1:
        dimension = Dimension.query.all()[0]
    elif count > 1:
        if 'DM_DIMENSION' in current_app.config:
            try:
                uuid.UUID(current_app.config['DM_DIMENSION'])
            except ValueError:
                dimension = Dimension.query.get(current_app.config['DM_DIMENSION'])
            else:
                dimension = Dimension.query.filter_by(name=current_app.config['DM_DIMENSION']).one_or_none()

    current_app.dimension_id = dimension.id if dimension else None

    current_app.before_request(load_global_data_into_context)

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
