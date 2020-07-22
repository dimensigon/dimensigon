import os
import signal
from functools import partial

from flask import Blueprint, request, current_app, jsonify, g
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_refresh_token_required, get_jwt_identity, \
    current_user

import dm
from dm import defaults
from dm.domain.entities import Server, Catalog
from dm.domain.entities.user import User
from dm.utils.helpers import get_now
from dm.web.decorators import forward_or_dispatch, validate_schema
from dm.web.json_schemas import schema_healthcheck, login_post

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
                "services": [],
                "server": {'id': str(g.server.id),
                           'name': g.server.name}
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
    req_data = request.json
    if req_data:
        req_data.update(dest_time=get_now().strftime(defaults.DATETIME_FORMAT))
        if 'servers' not in req_data:
            req_data.update(servers={})
    else:
        req_data = dict(dest_time=get_now().strftime(defaults.DATETIME_FORMAT))
    return req_data, 200


@root_bp.route('/login', methods=['POST'])
@forward_or_dispatch
@validate_schema(login_post)
def login():
    user = User.get_by_user(user=request.json.get('username', None))
    password = request.json.get('password', None)
    try:
        if not user or not user.verify_password(password):
            return {"error": "Bad username or password"}, 401
    except TypeError:
        return {"error": "Bad username or password"}, 401

    # Use create_access_token() and create_refresh_token() to create our
    # access and refresh tokens
    ret = {
        'access_token': create_access_token(identity=str(user.id), fresh=True),
        'refresh_token': create_refresh_token(identity=str(user.id))
    }
    return jsonify(ret), 200


@root_bp.route('/refresh', methods=['POST'])
@forward_or_dispatch
@jwt_refresh_token_required
def refresh():
    current_user_id = get_jwt_identity()
    ret = {
        'username': current_user.user,
        'access_token': create_access_token(identity=current_user_id, fresh=False)
    }
    return jsonify(ret), 200

@root_bp.route('/fresh-login', methods=['POST'])
@forward_or_dispatch
@validate_schema(login_post)
def fresh_login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    if username != 'test' or password != 'test':
        return jsonify({"msg": "Bad username or password"}), 401

    new_token = create_access_token(identity=username, fresh=True)
    ret = {'access_token': new_token}
    return jsonify(ret), 200