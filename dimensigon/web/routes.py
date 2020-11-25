import datetime as dt

from flask import Blueprint, request, current_app, jsonify, g
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_refresh_token_required, get_jwt_identity, \
    jwt_optional

import dimensigon
from dimensigon import defaults
from dimensigon.domain.entities import Server, Catalog, User
from dimensigon.utils.helpers import get_now
from dimensigon.web import errors
from dimensigon.web.decorators import forward_or_dispatch, validate_schema, securizer
from dimensigon.web.helpers import check_param_in_uri
from dimensigon.web.json_schemas import login_post, healthcheck_post

blueprint_name = 'root'
root_bp = Blueprint(blueprint_name, __name__)


@root_bp.route('/')
def home():
    return {'message': 'Welcome to dimensigon'}


@root_bp.route('/healthcheck', methods=['GET', 'POST'])
# @log_time('full')
@forward_or_dispatch()
@jwt_optional
@securizer
@validate_schema(POST=healthcheck_post)
# @log_time('after validation')
def healthcheck():
    if request.method == 'POST' and isinstance(g.source, Server):
        data = request.get_json()
        try:
            heartbeat = dt.datetime.strptime(data['heartbeat'], defaults.DATETIME_FORMAT)
        except:
            raise errors.InvalidDateFormat(data['heartbeat'], defaults.DATETIME_FORMAT)
        current_app.dm.cluster_manager.put(data['me'], heartbeat)

    catalog_ver = Catalog.max_catalog()
    data = {"version": dimensigon.__version__,
            "catalog_version": catalog_ver.strftime(defaults.DATEMARK_FORMAT) if catalog_ver else None,
            "services": [],

            }
    if not check_param_in_uri('human'):
        server = {'id': str(g.server.id), 'name': g.server.name}
        neighbours = [{'id': str(s.id), 'name': s.name} for s in Server.get_neighbours()]
        cluster = {'alive': current_app.dm.cluster_manager.get_alive(),
                   'in_coma': current_app.dm.cluster_manager.get_zombies()}
    else:
        server = g.server.name
        neighbours = sorted([s.name for s in Server.get_neighbours()])
        cluster = {'alive': sorted(
            [getattr(Server.query.get(i), 'name', i) for i in current_app.dm.cluster_manager.get_alive()]),
                   'in_coma': sorted(
                       [getattr(Server.query.get(i), 'name', i) for i in current_app.dm.cluster_manager.get_zombies()])}
    data.update(server=server, neighbours=neighbours, cluster=cluster,
                now=get_now().strftime(defaults.DATETIME_FORMAT))

    return data


@root_bp.route('/ping', methods=['POST'])
@forward_or_dispatch()
def ping():
    req_data = request.get_json()
    if req_data:
        req_data.update(dest_time=get_now().strftime(defaults.DATETIME_FORMAT))
        if 'servers' not in req_data:
            req_data.update(servers={})
    else:
        req_data = dict(dest_time=get_now().strftime(defaults.DATETIME_FORMAT))
    return req_data, 200


@root_bp.route('/login', methods=['POST'])
@forward_or_dispatch()
@validate_schema(login_post)
def login():
    user = User.get_by_name(name=request.get_json().get('username', None))
    password = request.get_json().get('password', None)
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
@forward_or_dispatch()
@jwt_refresh_token_required
def refresh():
    user = User.query.get(get_jwt_identity())
    ret = {
        'username': getattr(user, 'name', None),
        'access_token': create_access_token(identity=get_jwt_identity(), fresh=False)
    }
    return jsonify(ret), 200


@root_bp.route('/fresh-login', methods=['POST'])
@forward_or_dispatch()
@validate_schema(login_post)
def fresh_login():
    username = request.get_json().get('username', None)
    password = request.get_json().get('password', None)
    if username != 'test' or password != 'test':
        return jsonify({"msg": "Bad username or password"}), 401

    new_token = create_access_token(identity=username, fresh=True)
    ret = {'access_token': new_token}
    return jsonify(ret), 200
