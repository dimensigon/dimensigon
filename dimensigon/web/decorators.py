import base64
import functools
import ipaddress
import json
import logging
import socket
import time
import typing as t

import requests
import rsa
from flask import current_app, url_for, g, request
from flask_jwt_extended import get_jwt_claims
from jsonschema import validate

from dimensigon import defaults
from dimensigon.domain.entities import Server, Scope, User, Locker, State, Gate
from dimensigon.network.exceptions import NotValidMessage
from dimensigon.web.helpers import get_servers_from_scope
from dimensigon.use_cases.lock import lock_scope
from dimensigon.utils.helpers import get_now
from dimensigon.web import db, errors, network as ntwrk, executor, get_root_auth

if t.TYPE_CHECKING:
    import flask

forwarder_logger = logging.getLogger('dm.forwarder')
dm_logger = logging.getLogger('dm')


def save_if_hidden_ip(remote_addr: str, server: Server):
    """

    :param remote_addr: remote_addr to save
    :param server: server who has the remote_addr
    :return:
    """
    ip = ipaddress.ip_address(remote_addr)
    if not ip.is_loopback:
        def get_ip(dns: str):
            if dns is None:
                return
            else:
                try:
                    return ipaddress.ip_address(socket.gethostbyname(dns))
                except:
                    return

        gate = [gate for gate in server.gates if ip in (gate.ip, get_ip(gate.dns))]
        if not gate:
            try:

                with lock_scope(Scope.CATALOG):
                    for port in set([gate.port for gate in server.gates]):
                        gate = server.add_new_gate(dns_or_ip=remote_addr, port=port, hidden=True)
                        db.session.add(gate)
                    db.session.commit()
            except errors.NoServerToLock as e:
                def background_new_gate():
                    resp = None
                    gates = [dict(dns_or_ip=remote_addr, port=port, hidden=True) for port in
                             set([gate.port for gate in server.gates])]
                    for port in set([gate.port for gate in server.gates]):
                        resp = ntwrk.patch(f"{remote_addr}:{port}", 'api_1_0.serverresource',
                                           view_data=dict(server_id=server.id),
                                           json=dict(gates=gates),
                                           auth=get_root_auth(), timeout=30)
                        if resp.ok:
                            break
                    else:
                        logger.error(f"Unable to create external gate {server}->{remote_addr}."
                                     f" Reason: {resp}" if resp else "")
                    # create local to be able to contact node in case needed
                    # with bypass_datamark_update():
                    #     for g in gates:
                    #         gate = server.add_new_gate(**g)
                    #         gate.last_modified_at = defaults.INITIAL_DATEMARK
                    #     db.session.commit()

                executor.submit(background_new_gate)

            except errors.LockerError as e:
                dm_logger.error(f"Unable to lock catalog for saving {remote_addr} from {server}. Reason: {e}")
            except Exception:
                dm_logger.exception(f"Unable to save {remote_addr} from {server}")


def _proxy_request(request: 'flask.Request', destination: Server, verify=False) -> requests.Response:
    url = destination.url() + request.full_path
    req_data = request.get_json()

    if request.path == '/ping':
        server_data = {'id': str(g.server.id), 'name': g.server.name,
                       'time': get_now().strftime(defaults.DATETIME_FORMAT)}
        if req_data:
            if 'servers' not in req_data:
                req_data['servers'] = {}
            req_data['servers'].update({len(req_data['servers']) + 1: server_data})
        else:
            req_data = dict(servers={1: server_data})
    kwargs = {
        'json': req_data,
        'allow_redirects': False
    }

    headers = {key.lower(): value for key, value in request.headers.items()}

    # Let requests reset the host for us.
    if 'host' in headers:
        del headers['host']

    headers['d-source'] = headers.get('d-source', '') + ':' + str(g.server.id)

    kwargs['headers'] = headers

    cookies = request.cookies

    kwargs['cookies'] = cookies

    return requests.request(request.method, url, verify=verify, **kwargs)


def set_source():
    # not call get_or_raise to allow make requests without D-Source header
    if not hasattr(g, 'source'):
        source_id, proxies = (request.headers.get('D-Source', '') + ':').split(':', 1)
        proxies = proxies.strip(':')
        source = None
        if source_id:
            source = Server.query.get(source_id)
        # check hidden ip on server
        if proxies:
            lp = proxies.split(':')
            neighbour = None
            if lp[-1]:
                neighbour = Server.query.get(lp[-1])
            if neighbour:
                save_if_hidden_ip(request.remote_addr, neighbour)
        if not source:
            source = request.headers.get('D-Source') or request.remote_addr
        elif not proxies:
            save_if_hidden_ip(request.remote_addr, source)

        if not isinstance(source, Server):
            servers = db.session.query(Server).filter_by(deleted=False).join(Gate.server).filter(
                Gate.ip == source).all()
            if len(servers) == 1:
                source = servers[0]

        g.source = source


def forward_or_dispatch(*methods):
    def inner(func):
        from flask import request
        logger = logging.getLogger('dm.forwarder')

        @functools.wraps(func)
        def wrapper_decorator(*args, **kwargs):
            destination_id = None
            if 'D-Destination' in request.headers:
                destination_id = request.headers['D-Destination']
            else:
                # Get information from content
                # Code Compatibility. Use D-Destination header instead
                data = request.get_json()
                if data is not None and 'destination' in data:
                    destination_id = data.get('destination')

            if destination_id and destination_id != str(g.server.id) and (not methods or request.method in methods):
                destination: Server = Server.query.get(destination_id)
                if destination is None:
                    return errors.format_error_response(errors.EntityNotFound('Server', destination_id))
                try:
                    if destination.route.proxy_server or destination.route.gate:
                        logger.debug(f"Forwarding request {request.method} {request.full_path} to {destination.route}")
                        resp = _proxy_request(request=request, destination=destination)
                    else:
                        return errors.format_error_response(errors.UnreachableDestination(destination, g.server))
                except requests.exceptions.RequestException as e:
                    return errors.format_error_response(errors.ProxyForwardingError(destination, e))
                else:
                    return resp.content, resp.status_code, dict(resp.headers)

            else:

                value = func(*args, **kwargs)
                return value

        return wrapper_decorator

    return inner


def securizer(func):
    from flask import request
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):

        # cipher_key = session.get('cipher_key', None)
        cipher_key = None
        securizer_method = None

        if 'D-Securizer' in request.headers:
            securizer_method = request.headers.get('D-Securizer')
            if securizer_method == 'plain' and not current_app.config.get('SECURIZER_PLAIN', False):
                return {'error': 'plain data is not allowed'}, 406

        if request.method != 'GET':
            if request.is_json:
                if current_app.config.get('SECURIZER', False) and securizer_method != 'plain':
                    g.original_json = request.get_json()
                    cipher_key = base64.b64decode(
                        request.get_json().get('key')) if 'key' in request.get_json() else cipher_key

                    try:
                        if request.path == url_for('api_1_0.join'):
                            temp_pub_key = rsa.PublicKey.load_pkcs1(
                                request.get_json().pop('my_pub_key').encode('ascii'))
                            data = ntwrk.unpack_msg2(data=request.get_json(),
                                                     pub_key=temp_pub_key,
                                                     priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                                                     cipher_key=cipher_key)
                        else:
                            data = ntwrk.unpack_msg(data=request.get_json())
                    except (rsa.pkcs1.VerificationError, NotValidMessage) as e:
                        return {'error': str(e),
                                'message': request.get_json()}, 400

                    request._cached_data = json.dumps(data)
                    request._cached_json = (data, data)


            else:
                if request.data:
                    return {'error': 'Content Type must be application/json'}, 400

        rest = tuple()
        rv = func(*args, **kwargs)
        if isinstance(rv, tuple):
            len_rv = len(rv)

            if len_rv >= 2:
                rest = rv[1:]
                rv = rv[0]

        if rv is None:
            return rv

        if isinstance(rv, dict):

            if request.path == url_for('api_1_0.join'):
                rv = ntwrk.pack_msg2(data=rv, pub_key=temp_pub_key,
                                     priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                                     cipher_key=cipher_key)
            else:
                if securizer_method == 'plain' and current_app.config.get('SECURIZER_PLAIN', False):
                    pass
                else:
                    rv = ntwrk.pack_msg(data=rv)

        if isinstance(rv, list):
            if securizer_method == 'plain' and current_app.config.get('SECURIZER_PLAIN', False):
                pass
            else:
                rv = ntwrk.pack_msg(data=rv)

        if rest:
            rv = (rv,) + rest
        return rv

    return wrapper_decorator


def validate_schema(schema_name=None, **methods):
    from flask import request
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kw):
            schema = methods.get(request.method.upper()) or methods.get(request.method.lower()) or schema_name
            if schema:
                validate(request.get_json(), schema)
            return f(*args, **kw)

        return wrapper

    return decorator


def lock_catalog(f):
    @functools.wraps(f)
    def wrapper(*args, **kw):
        # check if applicant in jwt
        claims = get_jwt_claims()
        if claims:
            if claims.get('applicant'):
                locker = Locker.query.get(Scope.CATALOG)
                if locker.state == State.LOCKED and locker.applicant == claims.get('applicant'):
                    try:
                        ret = f(*args, **kw)
                    except Exception as e:
                        db.session.rollback()
                        raise
                    return ret

        servers = get_servers_from_scope(Scope.CATALOG)
        with lock_scope(Scope.CATALOG, servers):
            try:
                ret = f(*args, **kw)
            except Exception as e:
                db.session.rollback()
                raise
        return ret

    return wrapper


def rollback_on_error(f):
    @functools.wraps(f)
    def wrapper(*args, **kw):
        try:
            return f(*args, **kw)
        except Exception:
            db.session.rollback()
            raise

    return wrapper


def run_as(username: str):
    from flask import Flask
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # app resolution
            app = None
            if 'app' in kwargs:
                app = kwargs['app']
            else:
                for a in args:
                    if isinstance(a, Flask):
                        app = a
                        break
                else:
                    app = current_app
            if app:
                ctx = app.app_context()
                ctx.push()
            try:
                user = User.get_by_name(username)
                if user is None:
                    raise errors.EntityNotFound("User", username, ['name'])
                from flask_jwt_extended.utils import ctx_stack
                ctx_stack.top.jwt_user = user
                jwt = {'identity': str(user.id)}
                ctx_stack.top.jwt = jwt
                return f(*args, **kwargs)
            finally:
                db.session.close()
                if app:
                    ctx.pop()

        return wrapper

    return decorator


logger = logging.getLogger('dm.time')


def log_time(tag=''):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            start = time.time()
            r = f(*args, **kwargs)
            elapsed = time.time() - start
            logger.debug(
                f"{getattr(f, '__name__', '')}{f' ({tag}) ' if tag else ' '}took {elapsed} seconds to complete")
            return r

        return wrapper

    return decorator
