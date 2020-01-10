import base64
import functools

import rsa
from flask import current_app, request, session, url_for, g

from dm.domain.entities import Server
from dm.network.gateway import unpack_msg, pack_msg
from dm.web.errors import UnknownServer


def forward_or_dispatch(func):
    from flask import request
    from dm.network.gateway import proxy_request

    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        data = request.get_json()
        if data is None or 'destination' not in data or data.get('destination') == str(current_app.server.id):
            value = func(*args, **kwargs)
            return value
        else:
            server_id = data.get('destination')
            destination = Server.query.get(server_id)
            if destination:
                resp = proxy_request(request=request, destination=destination)
                return resp.raw.read(), resp.status_code, resp.headers
            else:
                return UnknownServer(server_id).format()

    return wrapper_decorator


def securizer(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        cipher_key = None
        if request.method != 'GET':
            if request.is_json:
                try:
                    cipher_key = base64.b64decode(request.json.get('key')) if 'key' in request.json else session.get(
                        'cipher_key', None)
                    data = unpack_msg(request.json,
                                      pub_key=getattr(getattr(current_app, 'dimension', None), 'public', None),
                                      priv_key=getattr(getattr(current_app, 'dimension', None), 'private', None),
                                      cipher_key=cipher_key)

                    for key, val in request.json.items():
                        setattr(g, key, val)
                    for key in list(request.json.keys()):
                        request.json.pop(key)
                    for key, val in data.items():
                        request.json[key] = val
                except rsa.pkcs1.VerificationError as e:
                    return {'error': str(e),
                            'message': request.get_json()}, 400
            else:
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
                if request.base_url == url_for('api_1_0.join'):
                    temp_pub_key = request.get_json().get('pub')
                    rv = pack_msg(data=rv, pub_key=temp_pub_key,
                                  priv_key=getattr(getattr(current_app, 'dimension', None), 'private', None),
                                  cipher_key=cipher_key)
                else:
                    rv = pack_msg(data=rv, pub_key=getattr(getattr(current_app, 'dimension', None), 'public', None),
                                  priv_key=getattr(getattr(current_app, 'dimension', None), 'private', None),
                                  cipher_key=cipher_key)

        if rest:
            rv = (rv,) + rest
        return rv

    return wrapper_decorator
