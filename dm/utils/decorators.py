import base64
import functools

import rsa
from flask import Response, session, url_for
from flask import g
from flask import request
from flask_restful import abort

import dm.framework.exceptions
from dm.network.gateway import unpack_msg, pack_msg
from dm.utils.helpers import get_logger


def logged(klass):
    klass.logger = get_logger(klass)
    return klass


def forward_or_dispatch(func):
    from flask import request
    from dm.network.gateway import proxy_request
    from dm.web import repo_manager
    from dm.web import interactor

    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        data = request.get_json()
        if data is None or data.get('destination') == str(interactor.server.id):
            value = func(*args, **kwargs)
            return value
        else:
            try:
                destination = repo_manager.ServerRepo.find(id_=data.get('destination'))
            except dm.framework.exceptions.NotFound as e:
                abort(Response({"message": "Server destination not found"}, status=400, mimetype='application/json'))
            # noinspection PyReference
            resp = proxy_request(request=request, destination=destination)
            return resp.raw.read(), resp.status_code, resp.headers

    return wrapper_decorator


def securizer(func):
    from dm.web import dimension
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        cipher_key = None
        if request.method != 'GET':
            if request.is_json:
                try:
                    cipher_key = base64.b64decode(request.json.get('key')) if 'key' in request.json else session.get(
                        'cipher_key', None)
                    data = unpack_msg(request.json, pub_key=dimension.pub, priv_key=dimension.priv,
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
                    rv = pack_msg(data=rv, pub_key=temp_pub_key, priv_key=dimension.priv, cipher_key=cipher_key)
                else:
                    rv = pack_msg(data=rv, pub_key=dimension.pub, priv_key=dimension.priv, cipher_key=cipher_key)

        if rest:
            rv = (rv,) + rest
        return rv

    return wrapper_decorator
