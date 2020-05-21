import base64
import concurrent
import datetime
import ipaddress
import json
import math
import os
import pickle
import re
import time
import typing as t
import uuid

from flask import request, current_app, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token, current_user
from pkg_resources import parse_version

import dm
from dm import defaults as d, defaults
from dm.domain.entities import Software, Server, SoftwareServerAssociation, Catalog, Route, StepExecution, \
    Orchestration, OrchExecution, User
from dm.utils import asyncio, subprocess
from dm.utils.event_handler import Event
from dm.utils.helpers import get_distributed_entities, is_iterable_not_string
from dm.utils.typos import Id
from dm.web import db, executor
from dm.web.api_1_0 import api_bp
from dm.web.async_functions import deploy_orchestration, async_send_file
from dm.web.background_tasks import update_table_routing_cost
from dm.web.decorators import securizer, forward_or_dispatch, validate_schema, lock_catalog
from dm.web.helpers import check_param_in_uri
from dm.web.json_schemas import launch_command_post, post_schema_routes, patch_schema_routes, \
    launch_orchestration_post, software_send
from dm.web.network import HTTPBearerAuth, post
from dm.web.network import async_post

if t.TYPE_CHECKING:
    from dm.use_cases.operations import IOperationEncapsulation


@api_bp.route('/')
def home():
    return "API v1.0 documentation page"


@api_bp.route('/join/public', methods=['GET'])
@jwt_required
def join_public():
    if current_user == User.get_by_user('join'):
        return g.dimension.public.save_pkcs1(), 200, {'content-type': 'application/octet-stream'}
    else:
        return {}, 401


@api_bp.route('/join', methods=['POST'])
@securizer
@jwt_required
@lock_catalog
def join():
    if current_user == User.get_by_user('join'):
        js = request.get_json()
        current_app.logger.debug(f"New server wanting to join: {js}")
        s = Server.from_json(js)
        external_ip = ipaddress.ip_address(request.remote_addr)
        if not external_ip.is_loopback and external_ip not in [g.ip for g in s.gates]:
            for port in set([g.port for g in s.gates]):
                s.add_new_gate(external_ip, port, hidden=True)

        Route(destination=s, cost=0)
        db.session.add(s)
        db.session.commit()
        catalog = fetch_catalog(datetime.datetime(datetime.MINYEAR, 1, 1))
        catalog.update(Dimension=g.dimension.to_json())
        catalog.update(me=str(Server.get_current().id))
        return catalog, 200
    else:
        return '', 401


@api_bp.route('/software/send', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
@validate_schema(software_send)
def software_send():
    # Validate Data
    data = request.get_json()

    software = Software.query.get_or_404(data['software_id'])

    dest_server = Server.query.get_or_404(data['dest_server_id'])

    ssa = SoftwareServerAssociation.query.filter_by(server=g.server, software=software).one_or_none()
    if not ssa:
        return {'error': f"no Software Server Association found for software {data['software_id']} and "
                         f"server {data['dest_server_id']}"}, 404

    chunk_size = min(data.get('chunk_size', d.CHUNK_SIZE), d.CHUNK_SIZE) * 1024
    max_senders = min(data.get('max_senders', d.MAX_SENDERS), d.MAX_SENDERS)
    chunks = math.ceil(ssa.software.size / chunk_size)

    auth = HTTPBearerAuth(create_access_token(get_jwt_identity()))

    json_msg = dict(software_id=str(software.id), num_chunks=chunks, dest_path=data.get('dest_path'))

    resp, code = post(dest_server, 'api_1_0.transferlist', json=json_msg, auth=auth)

    if code == 202:
        transfer_id = resp.get('transfer_id')
        current_app.logger.debug(
            f"Transfer {transfer_id} created. Sending software {software} to {dest_server}:{data.get('dest_path')}.")
    else:
        current_app.logger.error(f"Error on creating transfer on {dest_server.url('api_1_0.transferlist')}\n"
                                 f"Data: {json.dumps(json_msg, indent=4)}\n"
                                 f"Error: {resp}")
        transfer_id = None

    if transfer_id:
        file = os.path.join(ssa.path, software.filename)
        executor.submit(asyncio.run,
                        async_send_file(dest_server=dest_server, transfer_id=transfer_id, file=file,
                                        chunk_size=chunk_size, max_senders=max_senders, auth=auth))

        return {'transfer_id': transfer_id}, 202
    return {'error': f'unable to create transfer on {dest_server}',
            'message': str(resp) if isinstance(resp, Exception) else resp,
            'code': code}, 400


@api_bp.route('/software/dimensigon', methods=['GET'])
@forward_or_dispatch
@jwt_required
@securizer
def software_dimensigon():
    # sends the last software
    repo = current_app.config['SOFTWARE_REPO']
    max_version = None
    max_file = None
    for file in os.listdir(os.path.join(repo, 'dimensigon')):
        if 'dimensigon-' in file:
            m = re.search(r'v?\d+\.\d+[.-][ab]?\d+', file)
            if m and parse_version(m.group()) >= parse_version(max_version or dm.__version__):
                max_version = m.group()
                max_file = file
    if max_file:
        with open(os.path.join(repo, 'dimensigon', max_file), 'rb') as fh:
            return {'filename': max_file, 'version': max_version,
                    'content': base64.b64encode(fh.read()).decode('ascii')}, 200
    else:
        return {}, 204


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
@validate_schema(POST=post_schema_routes, PATCH=patch_schema_routes)
def routes():
    if request.method == 'GET':

        route_table = []
        for route in Route.query.join(Server.route).order_by(
                Server.name).all():
            route_table.append(route.to_json(human=check_param_in_uri('human')))
        data = {'route_list': route_table}
        if check_param_in_uri('human'):
            data.update(server=str(g.server))
        else:
            data.update(server_id=str(g.server.id))
        return data

    elif request.method == 'POST':
        data = request.get_json()
        new_routes = update_table_routing_cost(**data)
        db.session.commit()

        # if len(new_routes) > 0:
        #     def func_patch(app, *args, **kwargs):
        #         with app.app_context():
        #             patch(*args, **kwargs)
        #
        #     msg = {'server_id': str(Server.get_current().id),
        #            'route_list': [
        #                dict(destination_id=str(d.id),
        #                     proxy_server_id=str(getattr(r.proxy_server, 'id')) if getattr(r.proxy_server, 'id',
        #                                                                                   None) else None,
        #                     gate_id=str(getattr(r.gate, 'id')) if getattr(r.gate, 'id', None) else None,
        #                     cost=r.cost)
        #                for d, r in new_routes.items()
        #            ]}
        #
        #     for s in Server.get_neighbours():
        #         th = threading.Thread(target=func_patch, args=(current_app._get_current_object(), s, 'api_1_0.routes'),
        #                               kwargs={'json': msg,
        #                                       'headers': dict(Authorization=request.headers['Authorization'])})
        #         th.daemon = True
        #         th.start()

    # elif request.method == 'PATCH':
    #     data = request.get_json()
    #     current_app.logger.debug(f"New routes recived: {json.dumps(data, indent=4)}")
    #     likely_proxy_server = Server.query.get(data.get('server_id'))
    #     new_routes = []
    #     if not likely_proxy_server:
    #         return {"error": f"Server id '{data.get('server_id')}' not found"}, 404
    #     for new_route in data.get('route_list', []):
    #         target_server = Server.query.get(new_route.get('destination_id'))
    #         if target_server is None:
    #             current_app.logger.debug(f"Destination server unknown {new_route.get('destination_id')}")
    #             continue
    #         if target_server == g.server:
    #             # check if server has detected me as a neighbour
    #             if new_route.get('cost') == 0:
    #                 # server may be created without route (backward compatibility)
    #                 if likely_proxy_server.route is None:
    #                     likely_proxy_server.route = Route(destination=likely_proxy_server)
    #                 # check if I do not have it as a neighbour yet
    #                 if likely_proxy_server.route.cost != 0:
    #                     for gate in likely_proxy_server.gates:
    #                         if check_host(gate.dns or str(gate.ip), gate.port, timeout=1, retry=3, delay=0.5):
    #                             likely_proxy_server.route.proxy_server = None
    #                             likely_proxy_server.route.gate = gate
    #                             likely_proxy_server.route.cost = 0
    #                             new_routes.append(likely_proxy_server.route)
    #                             break
    #         else:
    #             # server may be created without route (backward compatibility)
    #             if target_server.route is None:
    #                 target_server.route = Route(destination=target_server)
    #             # process routes whose proxy_server is not me
    #             if str(g.server.id) != new_route.get('proxy_server_id'):
    #                 if target_server.route.proxy_server == likely_proxy_server and new_route.get('cost') is None:
    #                     cost, time = None, None
    #                 else:
    #                     cost, time = ping_server(target_server, g.server)  # check my route
    #                 if cost is not None:
    #                     # if new route has less cost than actual route, take it as my new route
    #                     if ((new_route.get('cost') or 999999) + 1) < cost:
    #                         target_server.route.proxy_server = likely_proxy_server
    #                         target_server.route.gate = None
    #                         target_server.route.cost = new_route.get('cost') + 1
    #                         new_routes.append(target_server.route)
    #                 else:
    #                     # if new route reaches the destination take it as a new one
    #                     if new_route.get('cost') is not None:
    #                         target_server.route.proxy_server = likely_proxy_server
    #                         target_server.route.gate = None
    #                         target_server.route.cost = new_route.get('cost') + 1
    #                     else:
    #                         # neither my route and the new route has access to the destination
    #                         target_server.route.gate, target_server.route.proxy_server, target_server.route.cost = None, None, None
    #                     new_routes.append(target_server.route)
    #
    #     # # Seek my routes whose gateway is the likely_proxy_server
    #     # for target_server in Server.query.join(Route.destination).filter(
    #     #         Route.proxy_server == likely_proxy_server).all():
    #     #     for new_route in data.get('route_list', []):
    #     #         if new_route.get('cost'):
    #     #             target_server.route.cost = new_route.get('cost') + 1
    #     #         else:
    #     #             target_server.route.gate, target_server.route.proxy_server, target_server.route.cost = None, None, None
    #     #         new_routes.append(target_server.route)
    #     db.session.commit()
    #
    #     # send new information in background
    #     if new_routes:
    #         def func_patch(app, *args, **kwargs):
    #             with app.app_context():
    #                 patch(*args, **kwargs)
    #
    #         msg = {'server_id': str(g.server.id),
    #                'route_list': [
    #                    r.to_json()
    #                    for r in new_routes]}
    #
    #         for s in Server.get_neighbours():
    #             if s != likely_proxy_server:
    #                 th = threading.Thread(target=func_patch,
    #                                       args=(current_app._get_current_object(), s, 'api_1_0.routes'),
    #                                       kwargs={'json': msg,
    #                                               'headers': dict(Authorization=request.headers['Authorization'])})
    #                 th.daemon = True
    #                 th.start()

    return {}, 204


def run_command_and_callback(operation: 'IOperationEncapsulation', params, source: Id, execution: Id, auth,
                             timeout=None):
    cp = operation.execute(params=params, timeout=timeout)

    execution = StepExecution.query.get(execution)
    source = Server.query.get(source)
    execution.load_completed_result(cp)
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.exception(f"Error on commit for execution {execution.id}")

    resp, code = post(server=source, view_or_url='api_1_0.events', view_data={'event_id': str(execution.id)},
                      json=execution.to_json(), auth=auth)
    if code != 202:
        current_app.logger.error(f"Error while sending result for execution {execution.id}: {code}, {resp}")
    return execution.to_json()


@api_bp.route('/launch/operation', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
def launch_operation():
    data = request.get_json()
    operation, params = pickle.loads(base64.b64decode(data['operation'].encode('ascii')))
    orch_exec_json = data['execution']
    orch_exec = OrchExecution.from_json(orch_exec_json)

    e = StepExecution(execution_server=g.server, step_id=data.get('step_id'),
                      source_server=g.source, orch_execution=orch_exec)
    db.session.add_all([orch_exec, e])
    db.session.commit()
    future = executor.submit(run_command_and_callback, operation, params, g.source.id, e.id,
                             HTTPBearerAuth(create_access_token(get_jwt_identity())),
                             timeout=data.get('timeout'))
    try:
        r = future.result(1)
    except concurrent.futures.TimeoutError:
        return {'execution_id': str(e.id)}, 202
    except Exception as e:
        current_app.logger.exception(
            f"Exception got when executing step {data.get('step_id')}. See logs for more information")
        return {'error': f"Exception got when executing step {data.get('step_id')}. See logs for more information"}, 500
    else:
        return r, 200


def search(server_or_granule, servers):
    try:
        uid = uuid.UUID(server_or_granule)
    except ValueError:
        server_list = [server for server in servers if server_or_granule in server.granules]
    else:
        server_list = [server for server in servers if server.id == uid]
    return server_list


@api_bp.route('/launch/orchestration/<orchestration_id>', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
@validate_schema(launch_orchestration_post)
def launch_orchestration(orchestration_id):
    orchestration = Orchestration.query.get_or_404(orchestration_id)
    params = request.get_json().get('params', {})
    hosts = request.get_json().get('hosts')

    a = set(orchestration.target)
    if not isinstance(hosts, dict):
        hosts = dict(all=hosts)
    b = set(hosts.keys())
    c = a - b
    if len(c) > 0:
        return {'error': f"Target(s) not specified: {', '.join(c)}"}, 404
    c = b - a
    if len(c) > 0:
        return {'error': f"Target(s) not in orchestration: {', '.join(c)}"}, 400

    servers = Server.query.all()
    # convert hosts into servers
    not_found = []
    for target, v in hosts.items():
        server_list = []
        if is_iterable_not_string(v):
            for vv in v:
                sl = search(vv, servers)
                if len(sl) == 0:
                    not_found.append(vv)
                else:
                    server_list.extend(sl)
        else:
            sl = search(v, servers)
            if len(sl) == 0:
                not_found.append(v)
            else:
                server_list.extend(sl)
        hosts[target] = server_list
    if not_found:
        return {'error': "Following granules or ids did not match to any server: " + ', '.join(not_found)}, 404

    # check param entries
    rest = orchestration.user_parameters - set(params.keys())
    if rest:
        rest = list(rest)
        rest.sort()
        return {'error': f"Parameter(s) not specified: {', '.join(rest)}"}, 404

    if not orchestration.steps:
        return {'error': 'orchestration does not have steps to execute.'}, 400

    # convert servers to id:
    execution_id = uuid.uuid4()
    hosts = {k: [server.id for server in servers] for k, servers in hosts.items()}
    future = executor.submit(deploy_orchestration, orchestration=orchestration.id, params=params, hosts=hosts,
                             auth=HTTPBearerAuth(create_access_token(get_jwt_identity())), execution=execution_id)
    try:
        r = future.result(1)
    except concurrent.futures.TimeoutError:
        return {'execution_id': execution_id}, 202
    except Exception as e:
        current_app.logger.exception(f"Exception got when executing orchestration {orchestration}")
        return {'error': 'error while executing orchestration. Check the logs.'}, 500
    else:
        if 'error' in r:
            return jsonify(r), 500
        return jsonify(r), 200


async def parallel_command_run(servers, data, auth):
    server_responses = {}
    for server in servers:
        server_responses[str(server.id)] = asyncio.create_task(
            async_post(server, 'api_1_0.launch_command', json=data, auth=auth))

    for server in servers:
        try:
            server_responses[str(server.id)] = await server_responses[str(server.id)]
        except Exception as e:
            server_responses[str(server.id)] = {'error': 'Exception raised: ' + str(e)}
    return server_responses


def wrap_sudo(user, cmd):
    return f"sudo -u {user} -i {cmd}"


@api_bp.route('/launch/command', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
@validate_schema(launch_command_post)
def launch_command():
    data = request.get_json()

    server_list = []
    if 'hosts' in data:
        not_found = []
        servers = Server.query.all()
        if data['hosts'] == 'all':
            server_list = servers
        elif is_iterable_not_string(data['hosts']):
            for vv in data['hosts']:
                sl = search(vv, servers)
                if len(sl) == 0:
                    not_found.append(vv)
                else:
                    server_list.extend(sl)
        else:
            sl = search(data['hosts'], servers)
            if len(sl) == 0:
                not_found.append(data['hosts'])
            else:
                server_list.extend(sl)
        if not_found:
            return {'error': "Following granules or ids did not match to any server: " + ', '.join(not_found)}, 404
    else:
        server_list.append(g.server)

    if re.search('rm\s+((-\w+|--[-=\w]*)\s+)*(-\w*[rR]\w*|--recursive)', data['command']):
        return {'error': 'rm with recursion is not allowed'}, 403
    data.pop('hosts', None)
    start = None
    resp = {}
    if g.server in server_list:
        start = time.time()
        server_list.pop(server_list.index(g.server))
        username = getattr(current_user, 'user', None)
        if not username:
            return {"error": f"User {get_jwt_identity()} not found"}, 404

        cmd = wrap_sudo(current_user, data['command'])
        future = executor.submit(subprocess.run, cmd,
                                 timeout=data.get('timeout', defaults.TIMEOUT_COMMAND),
                                 shell=True)

    resp_data = {}
    if server_list:
        resp = asyncio.run(
            parallel_command_run(server_list, data, auth=HTTPBearerAuth(create_access_token(get_jwt_identity()))))
        for s, r in resp.items():
            if r[1] == 200:
                if s in r[0]:
                    resp_data[s] = r[0][s]
                else:
                    resp_data[s] = r[0]
            else:
                resp_data[s] = {'error': {'status_code': r[1], 'response': r[0]}}

    if start:
        try:
            cp = future.result(data.get('timeout', defaults.TIMEOUT_COMMAND) + 1 - (time.time() - start))
        except (concurrent.futures.TimeoutError, subprocess.TimeoutExpired):
            resp_data[str(g.server.id)] = {
                'error': f"Command '{cmd}' timed out after {data.get('timeout', defaults.TIMEOUT_COMMAND)} seconds"}
        except Exception as e:
            current_app.logger.exception("Exception raised while trying to run command")
            resp_data[str(g.server.id)] = {'error': str(e)}
        else:
            resp_data[str(g.server.id)] = {'stdout': cp.stdout, 'stderr': cp.stderr, 'returncode': cp.returncode}
    return resp_data, 200


@api_bp.route('/events/<event_id>', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
def events(event_id):
    e = Event(event_id, data=request.get_json())
    current_app.events.dispatch(e)
    return {}, 202
