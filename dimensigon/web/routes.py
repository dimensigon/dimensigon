import datetime as dt

from flask import Blueprint, request, current_app, jsonify, g
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, \
    jwt_required

import dimensigon
from dimensigon import defaults
from dimensigon.domain.entities import Server, Catalog, User
from dimensigon.utils.helpers import get_now
from dimensigon.web import db, errors
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
@jwt_required(optional=True)
@securizer
@validate_schema(POST=healthcheck_post)
# @log_time('after validation')
def healthcheck():
    if request.method == 'POST' and isinstance(getattr(g, 'source', None), Server):
        data = request.get_json()
        try:
            heartbeat = dt.datetime.strptime(data['heartbeat'], defaults.DATETIME_FORMAT)
        except:
            raise errors.InvalidDateFormat(data['heartbeat'], defaults.DATETIME_FORMAT)
        current_app.dm.cluster_manager.put(data['me'], heartbeat)

    catalog_ver = Catalog.max_catalog()

    # Only authenticated mesh peers (g.source resolves to a known Server) or
    # JWT-authenticated users may see node identity and cluster topology.
    # Anonymous/unidentified callers get a minimal liveness response only, so
    # the node's Server UUID, version and neighbour/cluster maps are not leaked
    # to unauthenticated reconnaissance (CWE-200).
    trusted = isinstance(getattr(g, 'source', None), Server) or get_jwt_identity() is not None
    if not trusted:
        # Default: minimal liveness only — never leak node identity/topology to
        # anonymous callers (CWE-200). When the operator explicitly opts in via
        # HEALTHCHECK_PUBLIC_TOPOLOGY (e.g. the public demo cluster), expose a
        # NAMES-ONLY mesh view so the demo status page can render the cluster —
        # still no UUIDs, version or service detail.
        if not current_app.config.get('HEALTHCHECK_PUBLIC_TOPOLOGY', False):
            return {"status": "ok", "now": get_now().strftime(defaults.DATETIME_FORMAT)}
        try:
            alive_names = sorted([getattr(db.session.get(Server, i), 'name', str(i))
                                  for i in current_app.dm.cluster_manager.get_alive()])
        except Exception:
            alive_names = []
        me = g.server if isinstance(getattr(g, 'server', None), Server) else Server.get_current()
        return {"status": "ok",
                "now": get_now().strftime(defaults.DATETIME_FORMAT),
                "server": me.name if me else None,
                "neighbours": [{"name": s.name} for s in Server.get_neighbours()],
                "cluster": {"alive": alive_names}}

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
            [getattr(db.session.get(Server, i), 'name', i) for i in current_app.dm.cluster_manager.get_alive()]),
            'in_coma': sorted(
                [getattr(db.session.get(Server, i), 'name', i) for i in current_app.dm.cluster_manager.get_zombies()])}
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
@jwt_required(refresh=True)
def refresh():
    user = db.session.get(User, get_jwt_identity())
    ret = {
        'username': getattr(user, 'name', None),
        'access_token': create_access_token(identity=get_jwt_identity(), fresh=False)
    }
    return jsonify(ret), 200
