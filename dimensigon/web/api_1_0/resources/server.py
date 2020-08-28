from flask import request, g
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import Server
from dimensigon.web import errors, db
from dimensigon.web.decorators import securizer, forward_or_dispatch, lock_catalog, validate_schema
from dimensigon.web.helpers import filter_query, check_param_in_uri
from dimensigon.web.json_schemas import server_patch


class ServerList(Resource):

    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(Server, request.args)
        return [s.to_json(add_gates=check_param_in_uri('gates'),
                          human=check_param_in_uri('human'),
                          no_delete=True,
                          add_ignore=True) for s in
                query.all()]


class ServerResource(Resource):
    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self, server_id):
        return Server.query.get_or_404(server_id).to_json(add_gates=check_param_in_uri('gates'),
                                                          human=check_param_in_uri('human'),
                                                          no_delete=True,
                                                          add_ignore=True)

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

        if 'ignore_on_lock' in json_data:
            server.l_ignore_on_lock = json_data.get('ignore_on_lock')

        db.session.commit()

        return {}, 204

    @forward_or_dispatch
    @jwt_required
    @securizer
    @lock_catalog
    def delete(self, server_id):
        server = Server.query.get_or_404(server_id)

        if server == g.server:
            raise errors.ServerDeleteError
        server.delete()

        db.session.commit()

        return {}, 204
