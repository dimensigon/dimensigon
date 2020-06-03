from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.domain.entities import Server
from dm.web import errors, db
from dm.web.decorators import securizer, forward_or_dispatch, lock_catalog, validate_schema
from dm.web.helpers import filter_query, check_param_in_uri
from dm.web.json_schemas import server_patch


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

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(server_patch)
    @lock_catalog
    def patch(self, server_id):
        json_data = request.get_json()

        server = Server.query.get_or_404(server_id)
        new_granules = json_data.get('granules', [])
        if 'all' in new_granules:
            raise errors.KeywordReserved("'all' is a reserved granule")

        server.granules = list(set(server.granules) | set(new_granules))

        for gate in json_data.get('gates'):
            server.add_new_gate(gate['dns_or_ip'], gate['port'], gate.get('hidden'))

        db.session.commit()

        return {}, 204

