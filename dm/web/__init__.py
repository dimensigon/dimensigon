import functools
import uuid
from datetime import datetime
import typing as t

from flask import Flask, request, current_app
from flask_sqlalchemy import SQLAlchemy
from werkzeug.local import LocalProxy

import dm.framework.utils.dependency_injection as di
from config import config_by_name
from dm.network.gateway import proxy_request
from dm.web.extensions.context_app import ContextApp
from dm.web.extensions.repo_factory import Repo
from dm.domain.catalog_manager import CatalogManager
from dm.use_cases.interactor import Interactor
import dm.framework.exceptions
import dm.web.exceptions as exc

db = SQLAlchemy()
repo = Repo()
_catalog_manager = ContextApp(CatalogManager, (datetime,))
_interactor = ContextApp(Interactor)


def _get_catalog_manager() -> CatalogManager:
    return _catalog_manager.current


def _get_interactor() -> Interactor:
    return _interactor.current

# noinspection PyTypeChecker
catalog_manager: CatalogManager = LocalProxy(_get_catalog_manager)
# noinspection PyTypeChecker
interactor: Interactor = LocalProxy(_get_interactor)


def create_app(config=None):
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

    # repo
    db.init_app(app)
    repo.init_app(app)
    container = di.Container()
    _catalog_manager.init_app(app)
    _interactor.init_app(app)
    with app.app_context():
        repo.create_repos(container=container)

        catalog_manager.set_catalog(get_all=repo.CatalogRepo.all, get=repo.CatalogRepo.find,
                                    save=repo.CatalogRepo.create_and_add)

        # Interactor Entry Point
        try:
            server_name = app.config.get('SERVER_NAME', '')
            server, port = (server_name if ':' in server_name else server_name + ':').split(':')
            server = repo.ServerRepo.get_by_ip_or_name(server, port)
        except dm.framework.exceptions.NoResultFound as e:
            raise exc.ServerLookupError(
                f"Server '{server_name}' not found in repo. Specify SERVER_NAME=server_or_ip:port") from e
        interactor.set_catalog(catalog_manager)
        interactor.set_server(server)

        if 'DIMENSION' in app.config:
            try:
                uuid.UUID(app.config['DIMENSION'])
            except ValueError:
                try:
                    dimension = repo.DimensionRepo.get_by_name(app.config['DIMENSION'])
                except dm.framework.exceptions.NoResultFound as e:
                    dimension = None
            else:
                dimension = repo.DimensionRepo.find(app.config['DIMENSION'])
            interactor.set_dimension(dimension)

    # API version 0
    from dm.web.routes import root_bp
    from dm.web.api_1_0 import api_bp as api_1_0_bp
    app.register_blueprint(root_bp)
    app.register_blueprint(api_1_0_bp)

    return app
