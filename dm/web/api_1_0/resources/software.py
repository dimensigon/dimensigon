import os

from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.domain.entities import Software, Server, SoftwareServerAssociation
from dm.utils.helpers import md5
from dm.web import db
from dm.web.decorators import securizer, forward_or_dispatch, validate_schema
from dm.web.helpers import filter_query
from dm.web.json_schemas import post_software_schema, put_software_servers_schema, patch_software_schema


def set_software_server(soft, server, file, recalculate_data=False):
    if not os.path.exists(file):
        return {"error": f"file '{file}' not found"}, 404

    if soft.size is None or recalculate_data:
        try:
            soft.size = os.path.getsize(file)
            soft.checksum = md5(file)
        except Exception as e:
            return {"error": f"Error while trying to access file '{file}': {e}"}, 500
    return SoftwareServerAssociation(software=soft, server=server, path=os.path.dirname(file))


# /software

class SoftwareList(Resource):

    @securizer
    @jwt_required
    @forward_or_dispatch
    def get(self):
        query = filter_query(Software, request.args)
        return [soft.to_json() for soft in query.all()]

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(post_software_schema)
    def post(self):
        json = request.get_json()

        soft = Software(name=json['name'], version=json['version'], family=json['family'])
        if 'server_id' in json:
            server = Server.query.get_or_404(json['server_id'])
            set_software_server(soft, server, json['file'])
            soft.filename = os.path.basename(json['file'])

        db.session.add(soft)
        db.session.commit()
        return {'software_id': str(soft.id)}, 201


# /software/<software_id>
class SoftwareResource(Resource):
    @securizer
    @jwt_required
    @forward_or_dispatch
    def get(self, software_id):
        return Software.query.get_or_404(software_id).to_json()


# software/<software_id>/servers
class SoftwareServers(Resource):
    @securizer
    @jwt_required
    @forward_or_dispatch
    def get(self, software_id):
        soft = Software.query.get_or_404(software_id)
        return [ssa.server.to_json() for ssa in soft.ssas]

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(put_software_servers_schema)
    def put(self, software_id):
        json = request.get_json()

        soft = Software.query.get_or_404(software_id)

        # delete all associations
        soft.ssas = []

        for ssa_json in json:
            server = Server.query.get_or_404(ssa_json['server_id'])
            ssa = SoftwareServerAssociation(software=soft, server=server, path=ssa_json['path'])
            db.session.add(ssa)

        db.session.commit()

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(patch_software_schema)
    def patch(self, software_id):
        json = request.get_json()

        soft = Software.query.get_or_404(software_id)
        server = Server.query.get_or_404(json['server_id'])

        ssa = set_software_server(soft, server, json['file'], recalculate_data=json.get('recalculate_data', False))
        db.session.add(ssa)
        db.session.commit()
        return '', 204
