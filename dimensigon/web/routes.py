import datetime as dt

from flask import Blueprint, request, current_app, jsonify, g
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_refresh_token_required, get_jwt_identity, \
    current_user, jwt_optional

import dimensigon
from dimensigon import defaults
from dimensigon.domain.entities import Server, Catalog, Scope, User
from dimensigon.use_cases.helpers import get_servers_from_scope
from dimensigon.use_cases.lock import lock_scope
from dimensigon.utils.helpers import get_now
from dimensigon.web import errors
from dimensigon.web.decorators import forward_or_dispatch, validate_schema
from dimensigon.web.helpers import check_param_in_uri
from dimensigon.web.json_schemas import schema_healthcheck, login_post

blueprint_name = 'root'
root_bp = Blueprint(blueprint_name, __name__)


@root_bp.route('/')
def home():
    return {'message': 'Welcome to dimensigon'}


@root_bp.route('/healthcheck', methods=['GET', 'POST'])
@forward_or_dispatch
@jwt_optional
@validate_schema(POST=schema_healthcheck)
def healthcheck():
    if request.method == 'GET':
        # catalog_ver = current_app.catalog_manager.max_data_mark
        # if catalog_ver:
        #     catalog_ver = current_app.catalog_manager.max_data_mark.strftime(current_app.catalog_manager.format)
        catalog_ver = Catalog.max_catalog()
        data = {"version": dimensigon.__version__,
                "catalog_version": catalog_ver.strftime(defaults.DATEMARK_FORMAT) if catalog_ver else None,
                "scheduler": "running" if getattr(current_app.extensions.get('scheduler'), 'running',
                                                  None) else "stopped",

                "services": [],

                }
        if not check_param_in_uri('human'):
            server = {'id': str(g.server.id), 'name': g.server.name}
            neighbours = [{'id': str(s.id), 'name': s.name} for s in Server.get_neighbours()]
            cluster = {'alive': [current_app.cluster[i] for i in current_app.cluster],
                       'in_coma': [current_app.cluster[i] for i in current_app.cluster if i not in
                                   current_app.cluster.get_delta_keepalive(
                                       delta=dt.timedelta(
                                           minutes=defaults.REFRESH_PERIOD * defaults.COMA_NODE_FACTOR)) and i != g.server.id]}
        else:
            server = g.server.name
            neighbours = [s.name for s in Server.get_neighbours()]
            cluster = {'alive': [getattr(Server.query.get(i), 'name', i) for i in current_app.cluster],
                       'in_coma': [getattr(Server.query.get(i), 'name', i) for i in current_app.cluster if i not in
                                   current_app.cluster.get_delta_keepalive(
                                       delta=dt.timedelta(
                                           minutes=defaults.REFRESH_PERIOD * defaults.COMA_NODE_FACTOR)) and i != g.server.id]}

        data.update(server=server, neighbours=neighbours, cluster=cluster,
                    now=get_now().strftime(defaults.DATETIME_FORMAT))

        return data
    elif request.method == 'POST':
        user = User.get_current()
        if user and user.user == 'root':
            data = request.get_json()
            if 'alive' in data:
                server = Server.query.get(data.get('server_id', None))
                if server:
                    try:
                        servers = get_servers_from_scope(Scope.CATALOG, bypass=server)
                        with lock_scope(Scope.CATALOG, servers):
                            server.alive = data['alive']
                    except Exception:
                        server.alive = data['alive']

        else:
            raise errors.UserForbiddenError


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