import base64
import functools

import rsa
from flask import request, url_for, g, current_app
from jsonschema import validate, ValidationError

from dm.domain.entities import Server, Scope
from dm.network.exceptions import NotValidMessage
from dm.use_cases import exceptions as ue
from dm.use_cases.lock import lock, unlock
from dm.web import db
from dm.web.errors import UnknownServer
from dm.web.network import unpack_msg, pack_msg, unpack_msg2, pack_msg2


def forward_or_dispatch(func):
    from flask import request
    from dm.network.gateway import proxy_request

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
            if destination:
                resp = proxy_request(request=request, destination=destination)
                return resp.content, resp.status_code, dict(resp.headers)
            else:
                return UnknownServer(destination_id).format()
        else:
            g.source = db.session.query(Server).get(request.headers.get('D-Source')) or request.headers.get(
                'D-Source') or request.remote_addr
            value = func(*args, **kwargs)
            return value

    return wrapper_decorator


def securizer(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        # cipher_key = session.get('cipher_key', None)
        cipher_key = None
        if request.method != 'GET':
            if request.is_json:
                g.original_json = request.get_json()
                cipher_key = base64.b64decode(request.json.get('key')) if 'key' in request.json else cipher_key
                # session['cipher_key'] = cipher_key
                try:
                    if request.path == url_for('api_1_0.join'):
                        temp_pub_key = rsa.PublicKey.load_pkcs1(request.json.pop('my_pub_key').encode('ascii'))
                        data = unpack_msg2(request.get_json(),
                                           pub_key=temp_pub_key,
                                           priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                                           cipher_key=cipher_key)
                    else:
                        data = unpack_msg(request.get_json())
                except (rsa.pkcs1.VerificationError, NotValidMessage) as e:
                    return {'error': str(e),
                            'message': request.get_json()}, 400
                if current_app.config['SECURIZER'] and data:
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
            if 'error' not in rv:
                if request.path == url_for('api_1_0.join'):
                    rv = pack_msg2(data=rv, pub_key=temp_pub_key,
                                   priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                                   cipher_key=cipher_key)
                else:
                    rv = pack_msg(data=rv)

        if isinstance(rv, list):
            rv = pack_msg(data=rv)

        if rest:
            rv = (rv,) + rest
        return rv

    return wrapper_decorator


def validate_schema(schema_name=None, **methods):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kw):
            schema = methods.get(request.method.upper()) or methods.get(request.method.lower()) or schema_name
            if schema:
                try:
                    validate(request.json, schema)
                except ValidationError as e:
                    return {"error": str(e)}, 400
            return f(*args, **kw)

        return wrapper

    return decorator


def validate_schema(schema_name=None, **methods):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kw):
            schema = methods.get(request.method.upper()) or methods.get(request.method.lower()) or schema_name
            if schema:
                try:
                    validate(request.json, schema)
                except ValidationError as e:
                    return {"error": str(e)}, 400
            return f(*args, **kw)

        return wrapper

    return decorator


def lock_catalog(f):
    @functools.wraps(f)
    def wrapper(*args, **kw):
        try:
            applicant = lock(Scope.CATALOG)
            current_app.logger.debug(f"Lock on CATALOG acquired")
        except ue.ErrorLock as e:
            return e.to_json(), 400
        ret = f(*args, **kw)

        try:
            unlock(Scope.CATALOG, applicant=applicant)
        except ue.ErrorLock as e:
            current_app.logger.error(f"Error while trying to unlock: {e}")

        return ret

    return wrapper

