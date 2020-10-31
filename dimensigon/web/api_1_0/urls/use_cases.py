import base64
import concurrent
import copy
import datetime as dt
import functools
import ipaddress
import json
import logging
import math
import os
import pickle
import random
import re
import shlex
import time
import traceback
import typing as t
import uuid
from collections import OrderedDict

from flask import request, current_app, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from pkg_resources import parse_version

import dimensigon
import dimensigon.use_cases.clustering
import dimensigon.use_cases.routing as routing
import dimensigon.web.network as ntwrk
from dimensigon import defaults as d, defaults
from dimensigon.domain.entities import Software, Server, SoftwareServerAssociation, Catalog, Route, StepExecution, \
    Orchestration, OrchExecution, User, ActionTemplate, ActionType, Gate
from dimensigon.domain.entities.route import RouteContainer
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.use_cases.deployment import deploy_orchestration, validate_input_chain
from dimensigon.utils import asyncio, subprocess
from dimensigon.utils.dag import DAG
from dimensigon.utils.event_handler import Event
from dimensigon.utils.helpers import get_distributed_entities, is_iterable_not_string, md5, get_now, format_exception
from dimensigon.utils.var_context import Context
from dimensigon.web import db, executor, errors, threading
from dimensigon.web.api_1_0 import api_bp
from dimensigon.web.async_functions import async_send_file
from dimensigon.web.background_tasks import _async_get_neighbour_catalog_data_mark, \
    upgrade_version, \
    update_catalog
from dimensigon.web.decorators import securizer, forward_or_dispatch, validate_schema, lock_catalog, log_time
from dimensigon.web.helpers import check_param_in_uri, normalize_hosts, search, get_auth_from_request
from dimensigon.web.json_schemas import launch_command_post, routes_post, routes_patch, \
    launch_orchestration_post, send_post, orchestration_full, manager_server_ignore_lock_post, cluster_post

if t.TYPE_CHECKING:
    from dimensigon.use_cases.operations import IOperationEncapsulation


@api_bp.route('/')
def home():
    return "API v1.0 documentation page"


@api_bp.route('/join/token', methods=['GET'])
@jwt_required
def join_token():
    if get_jwt_identity() == '00000000-0000-0000-0000-000000000001':
        user_join = User.get_by_user('join')
        expire_time = request.args.get('expires_time', type=int, default=None)

        kwargs = {}
        if expire_time:
            kwargs['expires_delta'] = dt.timedelta(minutes=expire_time)

        return {'token': create_access_token(str(user_join.id), **kwargs)}, 200
    else:
        return {}, 401


@api_bp.route('/join/public', methods=['GET'])
@jwt_required
def join_public():
    if User.query.get(get_jwt_identity()) == User.get_by_user('join'):
        return g.dimension.public.save_pkcs1(), 200, {'content-type': 'application/octet-stream'}

    else:
        return {}, 401


servers_to_be_created = {}


def delete_old_temp_servers():
    global servers_to_be_created
    now = get_now()
    for s_id, data in list(servers_to_be_created.items()):
        s_created = dt.datetime.strptime(data['created_on'], defaults.DATETIME_FORMAT)
        if now - s_created > dt.timedelta(hours=1):
            servers_to_be_created.pop(s_id, None)


fetched_catalog = (get_now(), None)
_lock = threading.Lock()


@api_bp.route('/join', methods=['POST'])
@securizer
@jwt_required
def join():
    global fetched_catalog
    if get_jwt_identity() == '00000000-0000-0000-0000-000000000004':
        js = request.get_json()
        current_app.logger.debug(f"New server wanting to join: {json.dumps(js, indent=2)}")
        if db.session.query(Server).filter_by(id=js.get('id', None)).count() > 0:
            raise errors.DuplicatedId(js.get('id', None))
        if db.session.query(Server).filter_by(name=js.get('name', None)).count() > 0:
            raise errors.AlreadyExists('name', js.get('name', None))
        s = Server.from_json(js)
        s.created_on = get_now()
        external_ip = ipaddress.ip_address(request.remote_addr)
        if not external_ip.is_loopback and external_ip not in [gate.ip for gate in s.gates]:
            for port in set([gate.port for gate in s.gates]):
                s.add_new_gate(external_ip, port, hidden=True)

        certfile = current_app.dm.config.http_conf.get('certfile', None)
        keyfile = current_app.dm.config.http_conf.get('keyfile', None)

        if keyfile and os.path.exists(keyfile):
            with open(keyfile, 'rb') as fh:
                keyfile_content = fh.read()
        else:
            raise errors.FileNotFound(keyfile)
        if certfile and os.path.exists(certfile):
            with open(certfile, 'rb') as fh:
                certfile_content = fh.read()
        else:
            raise errors.FileNotFound(certfile)

        data = {'keyfile': base64.b64encode(keyfile_content).decode(),
                'certfile': base64.b64encode(certfile_content).decode()}

        data.update(Dimension=g.dimension.to_json())
        data.update(me=str(Server.get_current().id))

        with _lock:
            if fetched_catalog[1] is None or fetched_catalog[0] < get_now() - dt.timedelta(minutes=1):
                c = fetch_catalog(defaults.INITIAL_DATEMARK)
                fetched_catalog = (get_now(), c)
            else:
                c = fetched_catalog[1]
        data.update(catalog=c)

        server_data = s.to_json(add_gates=True)
        servers_to_be_created.update({s.id: server_data})
        del s
        return data, 200
    else:
        raise errors.GenericError('Invalid token', status_code=400)


_lock_add_node = threading.Lock()

@api_bp.route('/join/acknowledge/<server_id>', methods=['POST'])
@jwt_required
@lock_catalog
def join_acknowledge(server_id):
    server_data = servers_to_be_created.get(server_id, None)
    if not server_data:
        raise errors.EntityNotFound('Server', server_id)
    s = Server.from_json(server_data)
    with _lock_add_node:
        db.session.add(s)
        db.session.commit()
        current_app.logger.debug(f"Server join acknowledge {s.name}")
    return {}, 204


@api_bp.route('/manager/server_ignore_lock', methods=['POST'])
@forward_or_dispatch()
@jwt_required
@securizer
@validate_schema(manager_server_ignore_lock_post)
def internal_server():
    if get_jwt_identity() == '00000000-0000-0000-0000-000000000001':
        ignore = request.get_json()['ignore_on_lock']
        for server_id in request.get_json()['server_ids']:
            server = Server.query.get_or_raise(server_id)
            server.l_ignore_on_lock = ignore
            db.session.commit()

        return {}, 204
    else:
        raise errors.UserForbiddenError


@api_bp.route('/send', methods=['POST'])
@forward_or_dispatch()
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

    dest_server = Server.query.get_or_raise(json_data['dest_server_id'])

    if 'software_id' in json_data:
        software = Software.query.get_or_raise(json_data['software_id'])

        ssa = SoftwareServerAssociation.query.filter_by(server=g.server, software=software).one_or_none()
        # if current server does not have the software, forward request to the closest server who has it
        if not ssa:
            resp = ntwrk.get(dest_server, 'api_1_0.routes', auth=auth, timeout=5)
            if resp.code == 200:
                ssas = copy.copy(software.ssas)
                ssas.sort(key=functools.partial(search_cost, route_list=resp.msg['route_list']))
            # unable to get route cost, we take the first option we have
            else:
                ssas = random.shuffle(list(software.ssas))
            if len(ssas) == 0:
                raise errors.NoSoftwareServer(software_id=str(software.id))
            server = ssas[0].server  # closest server from dest_server who has the software

            resp = ntwrk.post(server, 'api_1_0.send', json=json_data, auth=auth)
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
        json_msg = dict(software_id=str(software.id), num_chunks=chunks)
        if 'dest_path' in json_data:
            json_msg['dest_path'] = json_data.get('dest_path')
    else:
        json_msg = dict(dest_path=json_data['dest_path'], filename=os.path.basename(json_data.get('file')), size=size,
                        checksum=checksum, num_chunks=chunks)
    # if dest_path not set, file will be sent to

    if 'force' in json_data:
        json_msg['force'] = json_data['force']

    resp = ntwrk.post(dest_server, 'api_1_0.transferlist', json=json_msg, auth=auth)
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
        resp = ntwrk.get(dest_server, "api_1_0.transferresource", view_data=dict(transfer_id=transfer_id), auth=auth)
        if resp.code == 200:
            msg = resp.msg
        else:
            resp.raise_if_not_ok()
    else:
        msg = {'transfer_id': transfer_id}
    return msg, 202 if json_data.get('background', True) else 201


@api_bp.route('/software/dimensigon', methods=['GET'])
@forward_or_dispatch()
@jwt_required
@securizer
def software_dimensigon():
    # sends the last software
    repo = os.path.join(current_app.dm.config.config_dir, defaults.SOFTWARE_REPO, defaults.DIMENSIGON_DIR)
    max_version = None
    max_file = None
    for file in os.listdir():
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
@forward_or_dispatch()
@jwt_required
@securizer
def catalog_update():

    data = asyncio.run(_async_get_neighbour_catalog_data_mark(get_now().strftime(defaults.DATETIME_FORMAT)))
    # check version upgrade before catalog upgrade to match database revision
    if not upgrade_version(data):
        update_catalog(data)
    db.session.commit()
    return {}, 204


@api_bp.route('/catalog/<string:data_mark>', methods=['GET', 'POST'])
@forward_or_dispatch()
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


@log_time()
def fetch_catalog(data_mark):
    data = {}
    now = get_now()
    for name, obj in get_distributed_entities():
        c = Catalog.query.get(name)
        # db.session.query to bypass deleted objects to spread deleted changes
        repo_data = obj.query.filter(obj.last_modified_at > data_mark).filter(
            obj.last_modified_at <= now).all()
        if name == 'User':
            data.update({name: [e.to_json(password=True) for e in repo_data]})
        else:
            data.update({name: [e.to_json() for e in repo_data]})
    return data


_cluster_logger = logging.getLogger('dimensigon.cluster')


@api_bp.route('/cluster', methods=['POST'])
@log_time('full')
# @forward_or_dispatch()
@jwt_required
@securizer
@log_time('after securizer')
@validate_schema(cluster_post)
@log_time('after validation')
def cluster():
    if get_jwt_identity() == '00000000-0000-0000-0000-000000000001':
        data = request.get_json()
        # _cluster_logger.debug(f"Data received {clustering.log_data(data)}")
        current_app.cluster_manager.put(data)
        return {}, 204
    else:
        raise errors.UserForbiddenError

async def background_cluster_in(server_id, routes, auth):
    server = Server.query.get(server_id)
    servers = Server.get_neighbours(exclude=server)
    # cluster information
    # if cr:
    #     tasks.append(clustering.send_cluster_register(cr, servers=servers, auth=auth))

    # route information
    changed_routes = {}

    # server might be sent cluster in message but not created in database
    if server:
        new_route = await routing.async_check_gates(server, timeout=5, retries=3, delay=2)
        if new_route and isinstance(new_route, RouteContainer):
            routing.logger.debug(f'cluster IN: New neighbour {server} found through {new_route.gate}')
            routing.set_route(server, new_route)
            changed_routes.update({server: new_route})
        else:
            routing.logger.debug(f"cluster IN: {server} is not a neighbour")
    try:
        changed_routes.update(
            routing.update_route_table_from_data({'server_id': server_id, 'route_list': routes}, auth))
    except errors.InvalidRoute as e:
        debug_new_routes = []
        routes.sort(key=lambda x: x.get('cost') or routing.MAX_COST, reverse=True)
        for new_route in routes:
            target_server = Server.query.get(new_route.get('destination_id'))
            proxy_server = Server.query.get(new_route.get('proxy_server_id'))
            gate = Gate.query.get(new_route.get('gate_id'))
            debug_new_route = dict(destination=getattr(target_server, 'name', new_route.get('destination_id')),
                                   proxy_server=getattr(proxy_server, 'name', new_route.get('proxy_server_id')),
                                   gate=str(gate) if gate else new_route.get('gate_id'),
                                   cost=new_route.get('cost'))
            debug_new_routes.append(debug_new_route)
            routing.logger.exception(
                "Error setting routes from following data: " + json.dumps(debug_new_routes, indent=4))
        raise

    if changed_routes:
        await routing.async_send_routes(changed_routes, auth=auth, servers=servers, exclude=server)


@api_bp.route('/cluster/in/<server_id>', methods=['POST'])
@jwt_required
@securizer
def cluster_in(server_id):
    user = User.get_current()
    if user and user.user == 'root':
        cr = current_app.cluster_manager.set_alive(server_id)
        _cluster_logger.debug(
            f"{getattr(Server.query.get(server_id), 'name', server_id) or server_id} is a new alive server")

        # run background execution to check routes
        executor.submit(asyncio.run, background_cluster_in(server_id, request.get_json(), get_auth_from_request()))

        return {'cluster': current_app.cluster_manager.cluster.get_cluster(),
                'neighbours': [s.id for s in Server.get_neighbours()]}, 200

    else:
        raise errors.UserForbiddenError


async def background_cluster_out(server_id, auth):
    servers = Server.get_neighbours(exclude=server_id)
    tasks = []

    # route information
    tasks.append(routing.async_remove_neighbour_send(server_id, auth=auth, servers=servers))
    await asyncio.gather(*tasks)


@api_bp.route('/cluster/out/<server_id>', methods=['POST'])
@jwt_required
@securizer
def cluster_out(server_id):
    user = User.get_current()
    if user and user.user == 'root':
        Server.query.get_or_raise(server_id)
        data = request.get_json()
        if data.get('death', None):
            try:
                death = dt.datetime.strptime(data['death'], defaults.DATEMARK_FORMAT)
            except:
                death = get_now()
        else:
            death = None
        current_app.cluster_manager.set_death(server_id, death=death)
        _cluster_logger.debug(f"{Server.query.get(server_id).name or server_id} is a death server")

        # run background route
        executor.submit(asyncio.run, background_cluster_out(server_id, get_auth_from_request()))

        return {}, 204
    else:
        raise errors.UserForbiddenError


# @api_bp.route('/routes/<server_id>', methods=['GET'])
# @forward_or_dispatch()
# @jwt_required
# @securizer
# def routes_neighbour(server_id):
#     server = Server.query.get_or_raise(server_id)
#     route = routing.check_neighbour(server)
#     # change server
#     if route:
#         return {'neighbour': True}
#     else:
#         return {'neighbour': False}


# set node to alive and check if neighbour

@api_bp.route('/routes', methods=['GET', 'POST', 'PATCH'])
@log_time('full')
@forward_or_dispatch('GET', 'POST')
@jwt_required
@securizer
@validate_schema(POST=routes_post, PATCH=routes_patch)
@log_time('after validation')
def routes():
    if request.method == 'GET':
        route_table = []
        for route in Route.query.join(Server.route).order_by(
                Server.name).filter(Server.deleted == False).all():
            route_table.append(route.to_json(human=check_param_in_uri('human')))
        data = {'route_list': route_table}
        data.update(server=dict(name=g.server.name, id=str(g.server.id)))
        return data

    elif request.method == 'POST':
        async def job(msg, auth):
            new_routes = await routing.async_update_route_table_cost(**msg)
            if len(new_routes) > 0:
                await routing.async_send_routes(auth=auth)
            return new_routes

        msg = request.get_json()
        if msg.get('background', False):
            executor.submit(asyncio.run, job(msg, get_auth_from_request()))
        else:
            asyncio.run(job(msg, HTTPBearerAuth(request.headers['Authorization'].split()[1])))
        return {}, 204

    elif request.method == 'PATCH':
        def job(msg, auth):
            new_routes = routing.update_route_table_from_data(msg, auth)
            if len(new_routes) > 0:
                exclude = msg.get('exclude', [])
                exclude.append(msg.get('server_id'))
                asyncio.run(routing.async_send_routes(new_routes, auth, exclude=exclude))

        executor.submit(job, request.get_json(), HTTPBearerAuth(request.headers['Authorization'].split()[1]))

        return {}, 204


def run_command_and_callback(operation: 'IOperationEncapsulation', params, context: Context, source: Server,
                             step_execution: StepExecution,
                             jwt_identity, event_id,
                             timeout=None):
    cp = operation.execute(params, timeout=timeout, context=context)

    execution = db.session.merge(step_execution)
    source = db.session.merge(source)
    execution.load_completed_result(cp)
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.exception(f"Error on commit for execution {execution.id}")
    data = dict(step_execution=execution.to_json())
    if execution.child_orch_execution:
        data['step_execution'].update(orch_execution=execution.child_orch_execution.to_json(add_step_exec=True))
    resp, code = ntwrk.post(server=source, view_or_url='api_1_0.events', view_data={'event_id': event_id},
                            json=data,
                            auth=HTTPBearerAuth(
                                create_access_token(jwt_identity, expires_delta=dt.timedelta(seconds=30))))
    if code != 202:
        current_app.logger.error(f"Error while sending result for execution {execution.id}: {code}, {resp}")
    return data


@api_bp.route('/launch/operation', methods=['POST'])
@forward_or_dispatch()
@jwt_required
@securizer
def launch_operation():
    data = request.get_json()
    operation = pickle.loads(base64.b64decode(data['operation'].encode('ascii')))
    var_context = pickle.loads(base64.b64decode(data['var_context'].encode('ascii')))
    params = pickle.loads(base64.b64decode(data['params'].encode('ascii')))
    orch_exec_json = data['orch_execution']
    orch_exec = OrchExecution.from_json(orch_exec_json)

    se = StepExecution(id=var_context.env.get('step_execution_id'), server=g.server, step_id=data.get('step_id'),
                       orch_execution=orch_exec, params=params,
                       start_time=get_now())
    db.session.add_all([orch_exec, se])
    db.session.commit()
    future = executor.submit(run_command_and_callback, operation, params, var_context, g.source, se,
                             get_jwt_identity(), data['event_id'],
                             timeout=data.get('timeout', None))
    try:
        r = future.result(1)
    except concurrent.futures.TimeoutError:
        return {}, 204
    except Exception as e:
        current_app.logger.exception(
            f"Exception got when executing step {data.get('step_id')}. See logs for more information")
        return {'error': f"Exception got when executing step {data.get('step_id')}. See logs for more information"}, 500
    else:
        return r, 200


@api_bp.route('/launch/orchestration/<orchestration_id>', methods=['POST'])
@forward_or_dispatch()
@jwt_required
@securizer
@validate_schema(launch_orchestration_post)
def launch_orchestration(orchestration_id):
    orchestration = Orchestration.query.get_or_raise(orchestration_id)
    data = request.get_json()
    params = data.get('params') or {}
    hosts = data.get('hosts')

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

    if data.get('input_validation', True):
        validate_input_chain(orchestration, params)

    vc = Context(params, dict(execution_id=None, parent_orch_execution_id=None, orch_execution_id=execution_id,
                              executor_id=get_jwt_identity()))

    if request.get_json().get('background', True):
        future = executor.submit(deploy_orchestration, orchestration=orchestration.id, var_context=vc, hosts=hosts,
                                 execution=execution_id)
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
            orch_exe = deploy_orchestration(orchestration=orchestration, var_context=vc, hosts=hosts,
                                            execution=execution_id)
        except Exception as e:
            current_app.logger.exception(f"Exception got when executing orchestration {orchestration}")
            raise
        else:

            return orch_exe.to_json(add_step_exec=True, human=check_param_in_uri('human'), split_lines=True), 200


def wrap_sudo(user, cmd):
    if isinstance(user, User):
        username = user.name
    else:
        username = user
    if isinstance(cmd, str):
        return f"sudo -Siu {username} -- sh -c {shlex.quote(cmd)}"
    else:
        args = ["sudo", "-Siu", username, "--", "bash" "-c",  shlex.quote(cmd)]
        return args


@api_bp.route('/launch/command', methods=['POST'])
@forward_or_dispatch()
@jwt_required
@securizer
@validate_schema(launch_command_post)
def launch_command():
    data = request.get_json()

    server_list = []
    if 'target' in data:
        not_found = []
        servers = Server.query.all()
        if data['target'] == 'all':
            server_list = servers
        elif is_iterable_not_string(data['target']):
            for vv in data['target']:
                sl = search(vv, servers)
                if len(sl) == 0:
                    not_found.append(vv)
                else:
                    server_list.extend(sl)
        else:
            sl = search(data['target'], servers)
            if len(sl) == 0:
                not_found.append(data['target'])
            else:
                server_list.extend(sl)
        if not_found:
            return {'error': "Following granules or ids did not match to any server: " + ', '.join(not_found)}, 404
    else:
        server_list.append(g.server)

    if re.search(r'rm\s+((-\w+|--[-=\w]*)\s+)*(-\w*[rR]\w*|--recursive)', data['command']):
        return {'error': 'rm with recursion is not allowed'}, 403
    data.pop('target', None)
    start = None

    username = getattr(User.query.get(get_jwt_identity()), 'user', None)
    if not username:
        raise errors.EntityNotFound('User', get_jwt_identity())
    cmd = wrap_sudo(username, data['command'])
    if g.server in server_list:
        start = time.time()
        server_list.pop(server_list.index(g.server))
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if data.get('input', None) else None, stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE, shell=True, close_fds=True, encoding='utf-8')

    resp_data = {}
    if check_param_in_uri("human"):
        attr = 'name'
    else:
        attr = 'id'
    if server_list:
        resp: t.List[ntwrk.Response] = asyncio.run(
            ntwrk.parallel_requests(server_list, method='POST', view_or_url='api_1_0.launch_command', json=data,
                                    auth=get_auth_from_request()))
        for s, r in zip(server_list, resp):
            key = getattr(s, attr, s.id)
            if r.ok:
                resp_data[key] = r.msg[s.id]
            else:
                if not r.exception:
                    resp_data[key] = {
                        'error': {'status_code': r.code, 'response': r.msg}}
                else:
                    if isinstance(r.exception, errors.BaseError):
                        resp_data[key] = errors.format_error_content(r.exception, current_app.config['DEBUG'])
                    else:
                        resp_data[key] = {
                            'error': format_exception(r.exception) if current_app.config['DEBUG'] else str(
                                r.exception) or str(r.exception.__class__.__name__)}

    if start:
        key = getattr(g.server, attr, g.server.id)
        timeout = data.get('timeout', defaults.TIMEOUT_COMMAND)
        try:
            outs, errs = proc.communicate(input=(data.get('input', '') or ''), timeout=timeout)
        except (TimeoutError, subprocess.TimeoutExpired):
            proc.kill()
            try:
                outs, errs = proc.communicate(timeout=1)
            except:
                resp_data[key] = {
                    'error': f"Command '{cmd}' timed out after {timeout} seconds. Unable to communicate with the process launched."}
            else:
                resp_data[key] = {
                    'error': f"Command '{cmd}' timed out after {timeout} seconds",
                    'stdout': outs.split('\n'), 'stderr': errs.split('\n')}
        except Exception as e:
            current_app.logger.exception("Exception raised while trying to run command")
            resp_data[key] = {
                'error': traceback.format_exc() if current_app.config['DEBUG'] else str(
                    r.exception) or str(r.exception.__class__.__name__)}
        else:
            resp_data[key] = {'stdout': outs.split('\n'), 'stderr': errs.split('\n'),
                                           'returncode': proc.returncode}
    resp_data['cmd'] = cmd
    resp_data['input'] = data.get('input', None)
    return resp_data, 200


@api_bp.route('/events/<event_id>', methods=['POST'])
@forward_or_dispatch()
@jwt_required
@securizer
def events(event_id):
    e = Event(event_id, data=request.get_json())
    current_app.events.dispatch(e)
    return {}, 202


@api_bp.route('/orchestrations/full', methods=['POST'])
@forward_or_dispatch()
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
            json_step['action_template'] = ActionTemplate.query.get_or_raise(json_step.pop('action_template_id'))
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
