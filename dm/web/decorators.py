import base64
import functools
import json

import rsa
from flask import request, session, url_for, g
from flask_jwt_extended import get_jwt_identity

from dm.domain.entities import Server
from dm.network.gateway import unpack_msg, pack_msg
from dm.web.errors import UnknownServer


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
                return resp.raw.read(), resp.status_code, resp.headers
            else:
                return UnknownServer(destination_id).format()
        else:
            value = func(*args, **kwargs)
            return value

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
                    if request.json:
                        if request.path == url_for('api_1_0.join'):
                            temp_pub_key = rsa.PublicKey.load_pkcs1(request.json.pop('my_pub_key').encode('ascii'))
                            data = unpack_msg(request.json,
                                              pub_key=temp_pub_key,
                                              priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                                              cipher_key=cipher_key)
                        else:
                            if get_jwt_identity() != 'test':
                                data = unpack_msg(request.json,
                                                  pub_key=getattr(getattr(g, 'dimension', None), 'public', None),
                                                  priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                                                  cipher_key=cipher_key)

                            try:
                                json.dumps(data)
                            except TypeError:
                                pass
                            else:
                                # data packed is still json. We recreate the request.json with the unpacked data
                                for key in list(request.json.keys()):
                                    request.json.pop(key)
                                for key, val in data.items():
                                    request.json[key] = val
                    else:
                        data = request.json
                    g.unpacked_data = data
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
                if request.path == url_for('api_1_0.join'):
                    rv = pack_msg(data=rv, pub_key=temp_pub_key,
                                  priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                                  cipher_key=cipher_key)
                else:
                    if get_jwt_identity() != 'test':
                        rv = pack_msg(data=rv, pub_key=getattr(getattr(g, 'dimension', None), 'public', None),
                                      priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                                      cipher_key=cipher_key)

        if isinstance(rv, list):
            if get_jwt_identity() != 'test':
                rv = pack_msg(data=rv, pub_key=getattr(getattr(g, 'dimension', None), 'public', None),
                              priv_key=getattr(getattr(g, 'dimension', None), 'private', None),
                              cipher_key=cipher_key)

        if rest:
            rv = (rv,) + rest
        return rv

    return wrapper_decorator

