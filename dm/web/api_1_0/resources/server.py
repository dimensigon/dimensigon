from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.domain.entities import Server
from dm.web.decorators import securizer, forward_or_dispatch
from dm.web.helpers import filter_query, check_param_in_uri


class ServerList(Resource):

    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(Server, request.args)
        return [at.to_json(add_gates=check_param_in_uri('gates'), human=check_param_in_uri('human')) for at in
                query.all()]


class ServerResource(Resource):
    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self, server_id):
        return Server.query.get_or_404(server_id).to_json(add_gates=check_param_in_uri('gates'),
                                                          human=check_param_in_uri('human'))
