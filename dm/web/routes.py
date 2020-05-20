import os
import signal
from functools import partial

from flask import Blueprint, request, current_app, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_refresh_token_required, get_jwt_identity

import dm
from dm import defaults
from dm.domain.entities import Server, Catalog
from dm.domain.entities.user import User
from dm.web.decorators import forward_or_dispatch, validate_schema
from dm.web.json_schemas import schema_healthcheck

blueprint_name = 'root'
root_bp = Blueprint(blueprint_name, __name__)


@root_bp.route('/')
def home():
    return {'message': 'Welcome to dimensigon'}


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        func = partial(os.kill, os.getppid(), signal.SIGTERM)
    current_app.logger.info('Shutting down server')
    current_app.scheduler.shutdown()
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


@root_bp.route('/healthcheck', methods=['GET', 'POST'])
@forward_or_dispatch
@validate_schema(POST=schema_healthcheck)
def healthcheck():
    if request.method == 'GET':
        # catalog_ver = current_app.catalog_manager.max_data_mark
        # if catalog_ver:
        #     catalog_ver = current_app.catalog_manager.max_data_mark.strftime(current_app.catalog_manager.format)
        catalog_ver = Catalog.max_catalog()
        return {"version": dm.__version__,
                "catalog_version": catalog_ver.strftime(defaults.DATEMARK_FORMAT) if catalog_ver else None,
                "scheduler": "running" if getattr(current_app.extensions.get('scheduler'), 'running',
                                                  None) else "stopped",
                "neighbours": [str(server) for server in Server.get_neighbours()],
                "services": []
                }
    elif request.method == 'POST':
        data = request.json

        if data.get('action') == 'stop':
            shutdown_server()
            return jsonify(''), 202
        elif data.get('action') == 'restart':
            return jsonify({'message': 'restart is not implemented'}), 500


@root_bp.route('/ping', methods=['POST'])
@forward_or_dispatch
def ping():
    resp = request.get_json()
    return jsonify({'hops': 0})


@root_bp.route('/login', methods=['POST'])
@forward_or_dispatch
def login():
    user = User.get_by_user(user=request.json.get('username', None))
    password = request.json.get('password', None)
    if not user or not user.verify_password(password):
        return {"error": "Bad username or password"}, 401

    # Use create_access_token() and create_refresh_token() to create our
    # access and refresh tokens
    ret = {
        'access_token': create_access_token(identity=str(user.id)),
        'refresh_token': create_refresh_token(identity=str(user.id))
    }
    return jsonify(ret), 200


@root_bp.route('/refresh', methods=['POST'])
@jwt_refresh_token_required
def refresh():
    current_user = get_jwt_identity()
    ret = {
        'access_token': create_access_token(identity=current_user)
    }
    return jsonify(ret), 200
