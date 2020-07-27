import base64
import concurrent
import copy
import datetime as dt
import functools
import ipaddress
import math
import os
import pickle
import random
import re
import time
import traceback
import typing as t
import uuid
from collections import OrderedDict

from flask import request, current_app, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token, current_user
from pkg_resources import parse_version

import dimensigon
from dimensigon import defaults as d, defaults
from dimensigon.domain.entities import Software, Server, SoftwareServerAssociation, Catalog, Route, StepExecution, \
    Orchestration, OrchExecution, User, ActionTemplate, ActionType
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.utils import asyncio, subprocess
from dimensigon.utils.dag import DAG
from dimensigon.utils.event_handler import Event
from dimensigon.utils.helpers import get_distributed_entities, is_iterable_not_string, md5, get_now
from dimensigon.utils.typos import Id
from dimensigon.utils.var_context import VarContext
from dimensigon.web import db, executor, errors
from dimensigon.web.api_1_0 import api_bp
from dimensigon.web.async_functions import deploy_orchestration, async_send_file
from dimensigon.web.background_tasks import update_table_routing_cost, _get_neighbour_catalog_data_mark, \
    upgrade_version, \
    update_catalog
from dimensigon.web.decorators import securizer, forward_or_dispatch, validate_schema, lock_catalog
from dimensigon.web.helpers import check_param_in_uri, normalize_hosts, search
from dimensigon.web.json_schemas import launch_command_post, routes_post, routes_patch, \
    launch_orchestration_post, send_post, orchestration_full
from dimensigon.web.network import async_post
from dimensigon.web.network import post, get

if t.TYPE_CHECKING:
    from dimensigon.use_cases.operations import IOperationEncapsulation


@api_bp.route('/')
def home():
    return "API v1.0 documentation page"


@api_bp.route('/join/public', methods=['GET'])
@jwt_required
def join_public():
    if current_user.user == User.get_by_user('join').user:
        return g.dimension.public.save_pkcs1(), 200, {'content-type': 'application/octet-stream'}
    else:
        return {}, 401


@api_bp.route('/join', methods=['POST'])
@securizer
@jwt_required
@lock_catalog
def join():
    if current_user.user == User.get_by_user('join').user:
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
        catalog = fetch_catalog(defaults.INITIAL_DATEMARK)
        catalog.update(Dimension=g.dimension.to_json())
        catalog.update(me=str(Server.get_current().id))
        return catalog, 200
    else:
        return '', 401


@api_bp.route('/send', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
@validate_schema(send_post)
def send():
    def search_cost(ssa, route_list):
        cost = [route['cost'] for route in route_list if str(ssa.server.id) == route['destination_id']]
        if cost:
            if cost[0] is None:
                cost = 999999
            else:
                cost = cost[0]
        else:
            cost = 999999
        return cost

    auth = HTTPBearerAuth(create_access_token(get_jwt_identity(), expires_delta=dt.timedelta(
        minutes=30)))
    # Validate Data
    json_data = request.get_json()

    dest_server = Server.query.get_or_404(json_data['dest_server_id'])

    if 'software_id' in json_data:
        software = Software.query.get_or_404(json_data['software_id'])

        ssa = SoftwareServerAssociation.query.filter_by(server=g.server, software=software).one_or_none()
        # if current server does not have the software, forward request to the closest server who has it
        if not ssa:
            resp = get(dest_server, 'api_1_0.routes', auth=auth, timeout=5)
            if resp.code == 200:
                ssas = copy.copy(software.ssas)
                ssas.sort(key=functools.partial(search_cost, route_list=resp.msg['route_list']))
            # unable to get route cost, we take the first option we have
            else:
                ssas = random.shuffle(list(software.ssas))
            if len(ssas) == 0:
                raise errors.NoSoftwareServer(software_id=str(software.id))
            server = ssas[0].server  # closest server from dest_server who has the software

            resp = post(server, 'api_1_0.send', json=json_data, auth=auth)
            resp.raise_if_not_ok()
            return resp.msg, resp.code
        else:

            file = os.path.join(ssa.path, software.filename)
            if not os.path.exists(file):
                raise errors.FileNotFound(file)
            size = ssa.software.size
    else:
        file = json_data['file']
        if os.path.exists(file):
            size = os.path.getsize(file)
            checksum = md5(json_data.get('file'))
        else:
            raise errors.FileNotFound(file)

    chunk_size = min(json_data.get('chunk_size', d.CHUNK_SIZE), d.CHUNK_SIZE) * 1024
    max_senders = min(json_data.get('max_senders', d.MAX_SENDERS), d.MAX_SENDERS)
    chunks = math.ceil(size / chunk_size)

    if 'software_id' in json_data:
        json_msg = dict(software_id=str(software.id), num_chunks=chunks,
                        dest_path=json_data.get('dest_path', current_app.config['SOFTWARE_REPO']))
    else:
        json_msg = dict(filename=os.path.basename(json_data.get('file')), size=size, checksum=checksum,
                        num_chunks=chunks, dest_path=json_data.get('dest_path', current_app.config['SOFTWARE_REPO']))
    if 'force' in json_data:
        json_msg['force'] = json_data['force']

    resp = post(dest_server, 'api_1_0.transferlist', json=json_msg, auth=auth)
    resp.raise_if_not_ok()

    transfer_id = resp.msg.get('id')
    current_app.logger.debug(
        f"Transfer {transfer_id} created. Sending {file} to {dest_server}:{json_data.get('dest_path')}.")

    if json_data.get('background', True):
        executor.submit(asyncio.run,
                        async_send_file(dest_server=dest_server, transfer_id=transfer_id, file=file,
                                        chunk_size=chunk_size, max_senders=max_senders, auth=auth))
    else:
        asyncio.run(async_send_file(dest_server=dest_server, transfer_id=transfer_id, file=file,
                                    chunk_size=chunk_size, max_senders=max_senders, auth=auth))

    if json_data.get('include_transfer_data', False):
        resp = get(dest_server, "api_1_0.transferresource", view_data=dict(transfer_id=transfer_id), auth=auth)
        if resp.code == 200:
            msg = resp.msg
        else:
            resp.raise_if_not_ok()
    else:
        msg = {'transfer_id': transfer_id}
    return msg, 202 if json_data.get('background', True) else 201


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
            if m and parse_version(m.group()) >= parse_version(max_version or dimensigon.__version__):
                max_version = m.group()
                max_file = file
    if max_file:
        with open(os.path.join(repo, 'dimensigon', max_file), 'rb') as fh:
            return {'filename': max_file, 'version': max_version,
                    'content': base64.b64encode(fh.read()).decode('ascii')}, 200
    else:
        return {}, 204


@api_bp.route('/catalog', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
def catalog_update():
    data = asyncio.run(_get_neighbour_catalog_data_mark())
    # check version upgrade before catalog upgrade to match database revision
    if not upgrade_version(data):
        update_catalog(data)
    db.session.commit()
    return {}, 204


@api_bp.route('/catalog/<string:data_mark>', methods=['GET', 'POST'])
@forward_or_dispatch
@jwt_required
@securizer
def catalog(data_mark):
    # Input Validation
    if data_mark == 'initial':
        data_validated = dt.datetime(dt.MINYEAR, 1, 1)
    else:
        try:
            data_validated = dt.datetime.strptime(data_mark, defaults.DATEMARK_FORMAT)
        except Exception as e:
            return {'error': f'Invalid Data Mark: {e}'}, 400

    return fetch_catalog(data_validated)


def fetch_catalog(data_mark):
    data = {}
    for name, obj in get_distributed_entities():
        c = Catalog.query.get(name)
        repo_data = obj.query.filter(obj.last_modified_at > data_mark).all()
        if name == 'User':
            data.update({name: [e.to_json(password=True) for e in repo_data]})
        else:
            data.update({name: [e.to_json() for e in repo_data]})
    return data


@api_bp.route('/routes', methods=['GET', 'POST', 'PATCH'])
@jwt_required
@securizer
@validate_schema(POST=routes_post, PATCH=routes_patch)
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


def run_command_and_callback(operation: 'IOperationEncapsulation', var_context, source: Id, execution: Id, jwt_identity,
                             timeout=None):
    cp = operation.execute(var_context=var_context, timeout=timeout)

    execution = StepExecution.query.get(execution)
    source = Server.query.get(source)
    execution.load_completed_result(cp)
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.exception(f"Error on commit for execution {execution.id}")
    data = dict(**execution.to_json(),
                                var_context=base64.b64encode(pickle.dumps(var_context)).decode('ascii'))
    resp, code = post(server=source, view_or_url='api_1_0.events', view_data={'event_id': str(execution.id)},
                      json=data,
                      auth=HTTPBearerAuth(
                          create_access_token(jwt_identity, expires_delta=dt.timedelta(seconds=30))))
    if code != 202:
        current_app.logger.error(f"Error while sending result for execution {execution.id}: {code}, {resp}")
    return data


@api_bp.route('/launch/operation', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
def launch_operation():
    data = request.get_json()
    operation = pickle.loads(base64.b64decode(data['operation'].encode('ascii')))
    var_context = pickle.loads(base64.b64decode(data['var_context'].encode('ascii')))
    orch_exec_json = data['execution']
    orch_exec = OrchExecution.from_json(orch_exec_json)

    e = StepExecution(server=g.server, step_id=data.get('step_id'), orch_execution=orch_exec, params=dict(var_context),
                      start_time=get_now())
    db.session.add_all([orch_exec, e])
    db.session.commit()
    future = executor.submit(run_command_and_callback, operation, var_context, g.source.id, e.id,
                             get_jwt_identity(),
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
        raise errors.TargetUnspecified(c)
    c = b - a
    if len(c) > 0:
        raise errors.TargetNotNeeded(c)

    not_found = normalize_hosts(hosts)
    if not_found:
        raise errors.ServerNormalizationError(not_found)

    for target, target_hosts in hosts.items():
        if len(target_hosts) == 0:
            raise errors.EmptyTarget(target)
    # check param entries
    # rest = orchestration.user_parameters - set(params.keys())
    # if rest:
    #     rest = list(rest)
    #     rest.sort()
    #     return {'error': f"Parameter(s) not specified: {', '.join(rest)}"}, 404

    if not orchestration.steps:
        return errors.GenericError('orchestration does not have steps to execute', orchestration_id=orchestration_id)

    execution_id = str(uuid.uuid4())

    vc = VarContext(globals=dict(execution_id=execution_id, executor_id=get_jwt_identity()), initials=params)

    if request.get_json().get('background', True):
        future = executor.submit(deploy_orchestration, orchestration=orchestration.id, var_context=vc, hosts=hosts)
        try:
            r = future.result(1)
        except concurrent.futures.TimeoutError:
            return {'execution_id': execution_id}, 202
        except Exception as e:
            current_app.logger.exception(f"Exception got when executing orchestration {orchestration}")
            raise
        else:
            return jsonify(r), 200
    else:
        try:
            orch_exe = deploy_orchestration(orchestration=orchestration.id, var_context=vc, hosts=hosts)
        except Exception as e:
            current_app.logger.exception(f"Exception got when executing orchestration {orchestration}")
            raise
        else:
            return orch_exe.to_json(add_step_exec=True, human=check_param_in_uri('human')), 200

async def parallel_command_run(servers, data, auth):
    server_responses = {}
    for server in servers:
        server_responses[str(server.id)] = asyncio.create_task(
            async_post(server, 'api_1_0.launch_command', json=data, auth=auth, timeout=data.get('timeout', None)))

    for server in servers:
        server_responses[str(server.id)] = await server_responses[str(server.id)]
    return server_responses


def wrap_sudo(user, cmd):
    if isinstance(user, User):
        username = user.name
    else:
        username = user
    if isinstance(cmd, str):
        return f"sudo -Siu {username} {cmd}"
    else:
        args = ["sudo", "-Siu", username]
        args.extend(cmd)
        return args


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

    if re.search(r'rm\s+((-\w+|--[-=\w]*)\s+)*(-\w*[rR]\w*|--recursive)', data['command']):
        return {'error': 'rm with recursion is not allowed'}, 403
    data.pop('hosts', None)
    start = None
    resp = {}
    username = getattr(current_user, 'user', None)
    if not username:
        raise errors.EntityNotFound('User', current_user)
    cmd = wrap_sudo(username, data['command'])
    if g.server in server_list:
        start = time.time()
        server_list.pop(server_list.index(g.server))
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if data.get('input', None) else None,
                                stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                                shell=True, close_fds=True)

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
                if r[1]:
                    resp_data[s] = {
                        'error': {'status_code': r[1], 'response': r[0] if isinstance(r[0], str) else str(r[0])}}
                else:
                    if current_app.config['DEBUG']:
                        f_tb = traceback.format_exception(type(r[0]), r[0], r[0].__traceback__)
                    else:
                        f_tb = traceback.format_exception_only(type(r[0]), r[0], r[0])
                    resp_data[s] = {'error': ''.join(f_tb)}

    if start:
        timeout = data.get('timeout', defaults.TIMEOUT_COMMAND)
        try:
            outs, errs = proc.communicate(input=(data.get('input', '') or '').encode(), timeout=timeout - (time.time() - start))
        except (TimeoutError, subprocess.TimeoutExpired):
            proc.kill()
            try:
                outs, errs = proc.communicate(timeout=1)
            except:
                resp_data[str(g.server.id)] = {
                    'error': f"Command '{cmd}' timed out after {timeout} seconds. Unable to communicate with the process."}
            else:
                resp_data[str(g.server.id)] = {
                    'error': f"Command '{cmd}' timed out after {timeout} seconds",
                    'stdout': outs.split('\n'), 'stderr': errs.split('\n')}
        except Exception as e:
            current_app.logger.exception("Exception raised while trying to run command")
            resp_data[str(g.server.id)] = {
                'error': traceback.format_exc() if current_app.config['DEBUG'] else traceback.format_exception_only()}
        else:
            resp_data[str(g.server.id)] = {'stdout': outs.decode().split('\n'), 'stderr': errs.decode().split('\n'),
                                           'returncode': proc.returncode}
    if check_param_in_uri("human"):
        convert_human = {}
        for s_id, r in resp_data.items():
            convert_human[Server.query.get(s_id).name] = r
        resp_data = convert_human
    resp_data['cmd'] = cmd
    resp_data['input'] = data.get('input', None)
    return resp_data, 200


@api_bp.route('/events/<event_id>', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
def events(event_id):
    e = Event(event_id, data=request.get_json())
    current_app.events.dispatch(e)
    return {}, 202


@api_bp.route('/orchestrations/full', methods=['POST'])
@forward_or_dispatch
@jwt_required
@securizer
@validate_schema(orchestration_full)
@lock_catalog
def orchestrations_full():
    json_data = request.get_json()
    json_steps = json_data.pop('steps')
    generated_version = False
    if 'version' not in json_data:
        generated_version = True
        json_data['version'] = Orchestration.query.filter_by(name=json_data['name']).count() + 1
    o = Orchestration(**json_data)
    db.session.add(o)
    resp_data = {'id': str(o.id)}
    if generated_version:
        resp_data.update(version=o.version)

    # reorder steps in order of dependency
    id2step = {str(s['id']): s for s in json_steps}

    dag = DAG()
    for s in json_steps:
        step_id = str(s['id'])
        if s['undo'] and len(s.get('parent_step_ids', [])) == 0:
            raise errors.UndoStepWithoutParent(step_id)
        dag.add_node(step_id)
        for p_s_id in s.get('parent_step_ids', []):
            dag.add_edge(str(p_s_id), step_id)

    if dag.is_cyclic():
        raise errors.CycleError

    new_steps = []
    for step_id in dag.ordered_nodes:
        step = id2step[step_id]
        new_steps.append(step)
    # end reorder steps in order of dependency

    rid2step = OrderedDict()
    dependencies = {}
    for json_step in new_steps:
        rid = str(json_step.pop('id', None))
        if rid is not None and rid in rid2step.keys():
            raise errors.DuplicatedId(rid)
        if 'action_template_id' in json_step:
            json_step['action_template'] = ActionTemplate.query.get_or_404(json_step.pop('action_template_id'))
        elif 'action_type' in json_step:
            json_step['action_type'] = ActionType[json_step.pop('action_type')]
        dependencies[rid] = {'parent_step_ids': [str(p_id) for p_id in json_step.pop('parent_step_ids', [])]}
        s = o.add_step(**json_step)
        db.session.add(s)
        if rid:
            rid2step[rid] = s

        continue

    # process dependencies
    for rid, dep in dependencies.items():
        step = rid2step[rid]
        parents = []
        for p_s_id in dep['parent_step_ids']:
            if p_s_id in rid2step:
                parents.append(rid2step[p_s_id])
        o.set_parents(step, parents)

    db.session.commit()

    # send new ids in order of appearance at beginning
    new_id_steps = []
    for rid in rid2step.keys():
        new_id_steps.append(str(rid2step[rid].id))
    resp_data.update({'step_ids': new_id_steps})
    return resp_data, 201
