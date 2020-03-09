import datetime
import threading
import uuid

import jsonschema
import requests
from flask import request, g, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from dm import defaults
from dm.domain.entities import Software, Server, SoftwareServerAssociation, Catalog, Route, Orchestration, Scope
from dm.use_cases.interactor import send_software, update_table_routing_cost
from dm.use_cases.lock import lock_scope
from dm.utils.helpers import get_distributed_entities
from dm.utils.talkback import Talkback
from dm.web import db
from dm.web.api_1_0 import api_bp
from dm.web.decorators import securizer, forward_or_dispatch
from dm.web.json_schemas import schema_software_send, schema_routes
from dm.web.network import ping as ping_server


@api_bp.route('/')
def home():
    return "API v1.0 documentation page"


@api_bp.route('/join/public', methods=['GET'])
@jwt_required
def join_public():
    if get_jwt_identity() == 'join':
        return g.dimension.public.save_pkcs1(), 200, {'content-type': 'application/octet-stream'}
    else:
        return '', 401


@api_bp.route('/software/send', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
def software_send():
    # Validate Data
    json = request.get_json()
    jsonschema.validate(json, schema_software_send)

    software = Software.query.get(json['software_id'])
    if not software:
        return {"error": f"Software id '{json['software_id']}' not found"}, 404
    dest_server = Server.query.get(json['dest_server_id'])
    if not dest_server:
        return {"error": f"Server id '{json['dest_server_id']}' not found"}, 404

    kwargs = {}

    if 'chunk_size' in json:
        kwargs.update(chunk_size=json.get('chunk_size'))
    if 'max_senders' in json:
        kwargs.update(max_senders=json.get('max_senders'))

    ssa = SoftwareServerAssociation.query.filter_by(server=dest_server, software=software)
    kwargs.update(ssa=ssa.id, dest_server=dest_server.id, dest_path=json.get('dest_path'))

    talk = Talkback()

    kwargs.update(talkback=talk)

    th = threading.Thread(target=send_software, name='send_software', kwargs=kwargs)
    th.start()
    if talk.wait_exists('transfer_id', timeout=40):
        return {'transfer_id': str(talk.get('transfer_id'))}, 202
    return {'error': 'unable to get transfer_id'}


@api_bp.route('/catalog/<string:data_mark>', methods=['GET', 'POST'])
@forward_or_dispatch
@jwt_required
@securizer
def catalog(data_mark):
    # Input Validation
    if data_mark == 'initial':
        data_validated = datetime.datetime(datetime.MINYEAR, 1, 1)
    else:
        try:
            data_validated = datetime.datetime.strptime(data_mark, defaults.DATEMARK_FORMAT)
        except Exception as e:
            return {'error': f'Invalid Data Mark: {e}'}, 400

    return fetch_catalog(data_validated)


def fetch_catalog(data_mark):
    data = {}
    for name, obj in get_distributed_entities():
        c = Catalog.query.get(name)
        repo_data = obj.query.filter(obj.last_modified_at > data_mark).all()
        # if repo_data:
        data.update({name: [e.to_json() for e in repo_data]})
    return data


@api_bp.route('/routes', methods=['GET', 'POST', 'PATCH'])
@jwt_required
@securizer
def routes():
    if request.method == 'GET':
        route_table = []
        for route in Route.query.filter(Route.destination != Server.get_current()).join(Route.destination).order_by(
                Server.name).all():
            route_table.append(route.to_json())
        return {'server_id': str(g.server.id),
                'route_list': route_table}
    elif request.method == 'POST':
        json = request.get_json()
        jsonschema.validate(json, schema_routes)
        kwargs = {}
        if 'discover_new_neighbours' in json:
            kwargs.update(discover_new_neighbours=json.get('discover_new_neighbours'))
        if 'check_current_neighbours' in json:
            kwargs.update(check_current_neighbours=json.get('check_current_neighbours'))

        new_routes = update_table_routing_cost(**kwargs)

        # send new information in background
        msg = {'server_id': str(g.server.id),
               'route_list': [
                   {'id': str(r.destination.id), 'gateway': str(r.gateway.id) if r.gateway else None, 'cost': r.cost}
                   for r in db.session.dirty
               ]}
        if len(db.session.dirty) > 0:
            for s in Server.get_neighbours():
                current_app.queue.register(requests.patch, async_proc_kw={'url': s.url('api_1_0.routes'), 'data': msg})

        db.session.commit()

    elif request.method == 'PATCH':
        # Validate Data
        json = request.get_json()
        jsonschema.validate(json, schema_routes)

        likely_gateway_server = Server.query.get(json.get('server_id'))
        new_routes = []
        if not likely_gateway_server:
            return {"error": f"Server id '{json.get('server_id')}' not found"}, 404
        for new_route in json.get('route_list', []):
            target_server = Server.query.get(new_route.get('destination'))
            # process routes whose gateway is g.server
            if str(g.server.id) != new_route.get('gateway'):
                cost, time = ping_server(target_server)
                if cost:
                    if new_route.get('cost') < cost:
                        target_server.route.gateway = likely_gateway_server
                        target_server.route.cost = new_route.get('cost') + 1
                        new_routes.append(target_server.route)
                else:
                    if new_route.get('cost'):
                        target_server.route.gateway = likely_gateway_server
                        target_server.route.cost = new_route.get('cost') + 1
                    else:
                        target_server.route.gateway, target_server.route.cost = None, None
                    new_routes.append(target_server.route)

        # Seek my routes whose gateway is the likely_gateway_server
        for target_server in Server.query.join(Route.destination).filter(Route.gateway == likely_gateway_server).all():
            for new_route in json.get('route_list', []):
                if new_route.get('cost'):
                    target_server.route.cost = new_route.get('cost') + 1
                else:
                    target_server.route.gateway = None
                    target_server.route.cost = None
                new_routes.append(target_server.route)
        db.session.commit()

        # send new information in background
        if new_routes:
            msg = {'server_id': str(g.server.id),
                   'route_list': [
                       {'destination': str(r.destination), 'gateway': str(r.gateway.id) if r.gateway else None,
                        'cost': r.cost}
                       for r in new_routes]}
            for s in Server.get_neighbours():
                if s != likely_gateway_server:
                    th = threading.Thread(target=requests.patch,
                                          kwargs={'url': s.url('api_1_0.routes'), 'json': msg,
                                                  'headers': dict(Authorization=request.headers['Authorization'])})
                    th.start()

    return '', 204


@api_bp.route('/launch/<string:orchestration_id>', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
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


@api_bp.route('/join', methods=['POST'])
@securizer
@jwt_required
def join():
    if get_jwt_identity() == 'join':
        js = request.get_json()
        current_app.logger.debug(f"New server wanting to join: {js}")
        s = Server.from_json(js)
        s.route.cost = 0
        with lock_scope(Scope.CATALOG):
            db.session.add(s)
            db.session.commit()
        dim = g.dimension.to_json()
        catalog = fetch_catalog(datetime.datetime(datetime.MINYEAR, 1, 1))
        catalog.update(Dimension=dim)
        catalog.update(me=str(Server.get_current().id))
        return catalog, 200
    else:
        return '', 401
