from flask import request, g
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import Server
from dimensigon.web import errors, db
from dimensigon.web.decorators import securizer, forward_or_dispatch, lock_catalog, validate_schema
from dimensigon.web.helpers import filter_query, check_param_in_uri
from dimensigon.web.json_schemas import server_patch, servers_delete


class ServerList(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(Server, request.args)
        return [s.to_json(add_gates=check_param_in_uri('gates'),
                          human=check_param_in_uri('human'),
                          no_delete=True,
                          add_ignore=True) for s in
                query.all()]

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(servers_delete)
    @lock_catalog
    def delete(self):
        servers = [Server.query.get_or_raise(s_id) for s_id in request.get_json()['server_ids']]
        for server in servers:
            if server == g.server:
                raise errors.ServerDeleteError
            # remove associated routes
            if server.route:
                db.session.delete(server.route)
            server.delete()
        db.session.commit()

        return {}, 204


class ServerResource(Resource):
    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self, server_id):
        return Server.query.get_or_raise(server_id).to_json(add_gates=check_param_in_uri('gates'),
                                                            human=check_param_in_uri('human'),
                                                            no_delete=True,
                                                            add_ignore=True)

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(server_patch)
    @lock_catalog
    def patch(self, server_id):
        json_data = request.get_json()
        resp_data = {}

        server = Server.query.get_or_raise(server_id)
        if 'all' in json_data.get('granules', []):
            raise errors.KeywordReserved("'all' is a reserved granule")

        new_granules = set(json_data.get('granules', [])) - set(server.granules)
        if new_granules:
            server.granules.extend(set(new_granules) - set(server.granules))

        new_gate_ids = []
        for gate in json_data.get('gates'):
            g = server.add_new_gate(gate['dns_or_ip'], gate['port'], gate.get('hidden'))
            new_gate_ids.append(g.id)
        if new_gate_ids:
            resp_data.update(gate_ids=new_gate_ids)

        if 'ignore_on_lock' in json_data:
            server.l_ignore_on_lock = json_data.get('ignore_on_lock')

        db.session.commit()

        if resp_data:
            return resp_data, 200
        else:
            return {}, 204

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @lock_catalog
    def delete(self, server_id):
        server = Server.query.get_or_raise(server_id)
        if server == g.server:
            raise errors.ServerDeleteError
        # remove associated routes
        db.session.delete(server.route)
        server.delete()
        db.session.commit()

        return {}, 204
