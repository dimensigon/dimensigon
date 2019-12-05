import functools
import uuid
from datetime import datetime
import typing as t

from flask import Flask, request, current_app
from flask_sqlalchemy import SQLAlchemy
from werkzeug.local import LocalProxy

import dm.framework.utils.dependency_injection as di
from config import config_by_name
from dm.domain.entities import Dimension
from dm.network.gateway import proxy_request
from dm.web.extensions.context_app import ContextApp
from dm.web.extensions.repo_factory import Repo
from dm.domain.catalog_manager import CatalogManager
from dm.use_cases.interactor import Interactor
import dm.framework.exceptions
import dm.web.exceptions as exc
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    get_jwt_identity
)

repo_manager = Repo()
_catalog_manager = ContextApp(CatalogManager, (datetime,))
_interactor = ContextApp(Interactor)
jwt = JWTManager()


def _get_catalog_manager() -> CatalogManager:
    return _catalog_manager.current


def _get_interactor() -> Interactor:
    return _interactor.current


__dimension_app_context = {}


def set_dimension(dimension_: Dimension):
    __dimension_app_context.update({current_app._get_current_object(): dimension_})


def _get_dimension() -> Dimension:
    return __dimension_app_context.get(current_app._get_current_object(), None)


# noinspection PyTypeChecker
catalog_manager: CatalogManager = LocalProxy(_get_catalog_manager)
# noinspection PyTypeChecker
interactor: Interactor = LocalProxy(_get_interactor)
# noinspection PyTypeChecker

# noinspection PyTypeChecker
dimension: Dimension = LocalProxy(_get_dimension)


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
    jwt.init_app(app)

    # repo
    db.init_app(app)
    repo_manager.init_app(app)
    container = di.Container()
    _catalog_manager.init_app(app)
    _interactor.init_app(app)
    with app.app_context():
        repo_manager.create_repos(container=container)

        catalog_manager.set_catalog(get_all=repo_manager.CatalogRepo.all, get=repo_manager.CatalogRepo.find,
                                    save=repo_manager.CatalogRepo.create_and_add)
        # register the catalog_manager on the container for injecting in RepoDataMark
        container.register_by_interface(interface=CatalogManager, constructor=catalog_manager, scope=di.Scopes.OBJECT)

        # Interactor Entry Point
        try:
            server_name = app.config.get('SERVER_NAME', '')
            server, port = (server_name if ':' in server_name else server_name + ':').split(':')
            server = repo_manager.ServerRepo.get_by_ip_or_name(server, port)
        except dm.framework.exceptions.NoResultFound as e:
            raise exc.ServerLookupError(
                f"Server '{server_name}' not found in repo. Specify SERVER_NAME=server_or_ip:port") from e
        interactor.set_catalog(catalog_manager)
        interactor.set_server(server)

        # Set Dimension
        if 'DIMENSION' in app.config:
            try:
                uuid.UUID(app.config['DIMENSION'])
            except ValueError:
                dimension_ = repo_manager.DimensionRepo.get_by_name(app.config['DIMENSION'])
            else:
                dimension_ = repo_manager.DimensionRepo.find(app.config['DIMENSION'])
        else:
            # check if only one dimension in repo
            dimensions = repo_manager.DimensionRepo.all()
            if len(dimensions) == 1:
                dimension_ = dimensions[0]
            elif len(dimensions) == 0:
                dimension_ = Dimension('PlainDimension', None, None, datetime.now())
            else:
                dimension_ = None
        set_dimension(dimension_)

    # API version 0
    from dm.web.routes import root_bp
    from dm.web.api_1_0 import api_bp as api_1_0_bp
    app.register_blueprint(root_bp)
    app.register_blueprint(api_1_0_bp)

    return app
