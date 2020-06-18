import base64
import functools
import ipaddress
import socket
import typing as t

import requests
import rsa
from flask import current_app, url_for, g
from jsonschema import validate

from dm.domain.entities import Server, Scope, User
from dm.network.exceptions import NotValidMessage
from dm.use_cases.helpers import get_servers_from_scope
from dm.use_cases.lock import lock_scope
from dm.web import db, errors
from dm.web.network import unpack_msg, pack_msg, unpack_msg2, pack_msg2

if t.TYPE_CHECKING:
    import flask


def save_if_hidden_ip(remote_addr: str, server: Server):
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
            hidden_gates = server.hidden_gates
            if hidden_gates:
                for hg in hidden_gates:
                    hg.ip = remote_addr
            else:
                for port in set([gate.port for gate in server.gates]):
                    gate = server.add_new_gate(dns_or_ip=remote_addr, port=port, hidden=True)
                    db.session.add(gate)
            db.session.commit()


def _proxy_request(request: 'flask.Request', destination: Server, verify=False) -> requests.Response:
    url = destination.url() + request.full_path
    json = request.get_json()

    if request.path == '/ping':
        json['hops'] = json.get('hops', 0) + 1

    kwargs = {
        'json': json,
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


def forward_or_dispatch(func):
    from flask import request

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

        if destination_id and destination_id != str(g.server.id):
            destination = Server.query.get(destination_id)
            if destination is None:
                return errors.format_error_response(errors.EntityNotFound('Server', destination_id))
            try:
                resp = _proxy_request(request=request, destination=destination)
            except requests.exceptions.RequestException as e:
                return errors.format_error_response(errors.ProxyForwardingError(destination, e))
            else:
                return resp.content, resp.status_code, dict(resp.headers)

        else:
            # not call get_or_404 to allow make requests without D-Source header
            source_id, proxies = (request.headers.get('D-Source', '') + ':').split(':', 1)
            proxies = proxies.strip(':')
            source = db.session.query(Server).get(source_id)
            # check hidden ip on server
            if proxies:
                lp = proxies.split(':')
                neighbour = db.session.query(Server).get(lp[-1])
                if neighbour:
                    save_if_hidden_ip(request.remote_addr, neighbour)
            if not source:
                source = request.headers.get('D-Source') or request.remote_addr
            elif not proxies:
                save_if_hidden_ip(request.remote_addr, source)
            g.source = source

            value = func(*args, **kwargs)
            return value

    return wrapper_decorator


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
                if securizer_method == 'plain':
                    pass
                else:
                    g.original_json = request.get_json()
                    cipher_key = base64.b64decode(request.json.get('key')) if 'key' in request.json else cipher_key
                    # session['cipher_key'] = cipher_key
                    try:
                        if request.path == url_for('api_1_0.join'):
                            temp_pub_key = rsa.PublicKey.load_pkcs1(request.json.pop('my_pub_key').encode('ascii'))
                            data = unpack_msg2(data=request.get_json(),
                                               pub_key=temp_pub_key,
                                               priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                                               cipher_key=cipher_key)
                        else:
                            data = unpack_msg(data=request.get_json())
                    except (rsa.pkcs1.VerificationError, NotValidMessage) as e:
                        return {'error': str(e),
                                'message': request.get_json()}, 400
                    if current_app.config.get('SECURIZER', None) and data:
                        # fill json request with unpacked data
                        for key in list(request.json.keys()):
                            request.json.pop(key)
                        for key, val in data.items():
                            request.json[key] = val

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
                rv = pack_msg2(data=rv, pub_key=temp_pub_key,
                               priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                               cipher_key=cipher_key)
            else:
                if securizer_method == 'plain' and current_app.config.get('SECURIZER_PLAIN', False):
                    pass
                else:
                    rv = pack_msg(data=rv)

        if isinstance(rv, list):
            if securizer_method == 'plain' and current_app.config.get('SECURIZER_PLAIN', False):
                pass
            else:
                rv = pack_msg(data=rv)

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
                validate(request.json, schema)
            return f(*args, **kw)

        return wrapper

    return decorator


def lock_catalog(f):
    @functools.wraps(f)
    def wrapper(*args, **kw):
        servers = get_servers_from_scope(Scope.CATALOG)
        with lock_scope(Scope.CATALOG, servers):
            ret = f(*args, **kw)
        return ret

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
            if app:
                ctx = app.app_context()
                ctx.push()
            try:
                user = User.get_by_user(username)
                if user is None:
                    raise errors.EntityNotFound("User", username, ['name'])
                from flask_jwt_extended.utils import ctx_stack
                ctx_stack.top.jwt_user = user
                jwt = {'identity': str(user.id)}
                ctx_stack.top.jwt = jwt
                return f(*args, **kwargs)
            finally:
                if app:
                    ctx.pop()

        return wrapper

    return decorator
