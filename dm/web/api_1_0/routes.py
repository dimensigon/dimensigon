import uuid
from datetime import datetime

import jsonschema
import requests
from flask import current_app, request
from flask_jwt_extended import jwt_required

from dm.domain.entities import Server, Orchestration
# from dm.use_cases.interactor import update_table_routing
from dm.utils.helpers import convert
from dm.web import db
from dm.web.decorators import forward_or_dispatch, securizer
from dm.web.api_1_0 import api_bp
from dm.use_cases.interactor import update_table_routing_cost
from dm.network.gateway import ping as ping_server


@api_bp.route('/')
def home():
    return "API v1.0 documentation page"


@api_bp.route('/join', methods=['POST'])
@jwt_required
@securizer
def join():
    return current_app.dimension


@api_bp.route('/launch/<string:orchestration_id>', methods=['POST'])
@securizer
@jwt_required
@forward_or_dispatch
def launch_orchestration(orchestration_id):
    # Input Validation
    try:
        orchestration_id = uuid.UUID(orchestration_id)
    except ValueError:
        return {'error': f'Invalid uuid: {orchestration_id}'}, 400
    o = Orchestration.query.get(orchestration_id)
    if not o:
        return {'error': f"Orchestration not found {orchestration_id}"}, 404

    # Logic


@api_bp.route('/catalog/<string:data_mark>', methods=['GET', 'POST'])
@securizer
@jwt_required
@forward_or_dispatch
def catalog(data_mark):
    # Input Validation
    try:
        data_validated = datetime.strptime(data_mark, '%Y%m%d%H%M%S%f')
    except Exception as e:
        return {'error': f'Invalid Data Mark: {e}'}, 400

    # Logic
    data = current_app.interactor.mediator.local_get_delta_catalog(data_validated)
    return data


UUID_pattern = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
schema_routes = {
    "type": "object",
    "properties": {
        "discover_new_neighbours": {"type": "boolean"},
        "check_current_neighbours": {"type": "boolean"},
        "server_id": {"type": "string",
                      "pattern": UUID_pattern},
        "server_list": {"type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "pattern": UUID_pattern},
                                "gateway": {"anyOf": [
                                    {"type": "string",
                                     "pattern": UUID_pattern},
                                    {"type": "null"}
                                ]},
                                "cost": {"anyOf": [
                                    {"type": "integer",
                                     "minimum": 0},
                                    {"type": "null"}
                                ]}
                            },
                            "required": ["id", "gateway", "cost"]
                        }
                        }
    }
}


@api_bp.route('/routes', methods=['GET', 'POST', 'PATCH'])
@securizer
@jwt_required
def routes():
    if request.method == 'GET':
        route_table = []
        for server in Server.query.filter(Server.id != current_app.server.id).filter().order_by(Server.name).all():
            route_table.append(server.to_json())
        return {'server_id': str(current_app.server.id),
                'server_list': route_table}
    elif request.method == 'POST':
        json = request.get_json()
        jsonschema.validate(json, schema_routes)
        kwargs = {}
        if 'discover_new_neighbours' in json:
            kwargs.update(discover_new_neighbours=json.get('discover_new_neighbours'))
        if 'check_current_neighbours' in json:
            kwargs.update(check_current_neighbours=json.get('check_current_neighbours'))

        update_table_routing_cost(**kwargs)

        # send new information in background
        msg = {'server_id': str(current_app.server.id),
               'server_list': [
                   {'id': str(s.id), 'gateway': str(s.gateway.id) if s.gateway else None, 'cost': s.cost}
                   for s in db.session.dirty
               ]}
        if len(db.session.dirty) > 0:
            for s in Server.get_neighbours():
                current_app.queue.register(requests.patch, async_proc_kw={'url': s.url('api_1_0.routes'), 'data': msg})

        db.session.commit()

    elif request.method == 'PATCH':
        # Validate Data
        json = request.get_json()
        jsonschema.validate(json, schema_routes)

        likely_gateway = Server.query.get(json.get('server_id'))
        new_routes = []
        if not likely_gateway:
            return {"error": f"Server id '{json.get('server_id')}' not found"}, 404
        for new_route in json.get('server_list'):
            target_server = Server.query.get(new_route.get('id'))
            # seek routes whose gateway is current_app.server
            if str(current_app.server.id) != new_route.get('gateway'):
                cost, time = ping_server(target_server)
                if time:
                    if new_route.get('cost') < cost:
                        target_server.gateway = likely_gateway
                        target_server.cost = new_route.get('cost') + 1
                        new_routes.append(target_server)
                else:
                    if new_route.get('cost'):
                        target_server.gateway = likely_gateway
                        target_server.cost = new_route.get('cost') + 1
                    else:
                        target_server.gateway, target_server.cost = None, None
                    new_routes.append(target_server)

        # Seek my routes whose gateway is the likely_gateway
        for target_server in Server.query.filter(Server.gateway == likely_gateway).all():
            for new_route in json.get('server_list'):
                if new_route.get('cost'):
                    target_server.cost = new_route.get('cost') + 1
                else:
                    target_server.gateway = None
                    target_server.cost = None
                new_routes.append(target_server)
        db.session.commit()

        # send new information in background
        if new_routes:
            msg = {'server_id': str(current_app.server.id),
                   'server_list': [
                       {'id': str(r.id), 'gateway': str(r.gateway.id) if r.gateway else None, 'cost': r.cost}
                       for r in new_routes]}
            for s in Server.get_neighbours():
                if s != likely_gateway:
                    current_app.queue.register(requests.patch,
                                               async_proc_kw={'url': s.url('api_1_0.routes'), 'data': msg})

    return '', 204
