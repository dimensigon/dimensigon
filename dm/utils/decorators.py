import functools

from flask import Response
from flask_restful import abort

import dm.framework.exceptions
from dm.utils.helpers import get_logger


def logged(klass):
    klass.logger = get_logger(klass)
    return klass


def forward_or_dispatch(func):
    from flask import request
    from dm.network.gateway import proxy_request
    from dm.web import repo
    from dm.web import interactor

    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        data = request.get_json()
        if data.get('destination') == str(interactor.server.id):
            value = func(*args, **kwargs)
            return value
        else:
            try:
                destination = repo.ServerRepo.find(id_=data.get('destination'))
            except dm.framework.exceptions.NotFound as e:
                abort(Response({"message": "Server destination not found"}, status=400, mimetype='application/json'))
            resp = proxy_request(request=request, destination=destination)
            return resp.content, resp.status_code, resp.headers

    return wrapper_decorator
