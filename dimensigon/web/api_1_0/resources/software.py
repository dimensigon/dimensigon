import os

from flask import request, g
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import Software, Server, SoftwareServerAssociation
from dimensigon.utils.helpers import md5
from dimensigon.web import db, errors
from dimensigon.web.decorators import securizer, forward_or_dispatch, validate_schema, lock_catalog
from dimensigon.web.helpers import filter_query, check_param_in_uri
from dimensigon.web.json_schemas import software_post, software_patch


def set_software_server(soft, server, path, recalculate_data=False):
    file = os.path.join(path, soft.filename)
    if not os.path.exists(file):
        raise errors.FileNotFound(file)

    if soft.size != os.path.getsize(file):
        return errors.GenericError(f"file is not of specified size", file=file, size=soft.size)
    if soft.checksum != md5(file):
        return errors.GenericError(f"checksum error on file", file=file)

    return SoftwareServerAssociation(software=soft, server=server, path=path)


# /software

class SoftwareList(Resource):

    @jwt_required
    @securizer
    @forward_or_dispatch()
    def get(self):
        query = filter_query(Software, request.args)
        return [soft.to_json(servers=check_param_in_uri('servers')) for soft in query.all()]

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(software_post)
    @lock_catalog
    def post(self):
        json = request.get_json()

        file = json['file']
        if not os.path.exists(file):
            raise errors.FileNotFound(file)

        soft = Software(name=json['name'], version=json['version'], filename=os.path.basename(json['file']),
                        size=os.path.getsize(file), checksum=md5(file),
                        family=json.get('family', None))
        ssa = set_software_server(soft, g.server, os.path.dirname(json['file']))

        if not isinstance(ssa, SoftwareServerAssociation):
            return ssa
        db.session.add_all([soft, ssa])
        db.session.commit()
        return {'id': str(soft.id)}, 201


# /software/<software_id>
class SoftwareResource(Resource):
    @jwt_required
    @securizer
    @forward_or_dispatch()
    def get(self, software_id):
        return Software.query.get_or_raise(software_id).to_json()


# software/<software_id>/servers
class SoftwareServersResource(Resource):
    @jwt_required
    @securizer
    @forward_or_dispatch()
    def get(self, software_id):
        soft = Software.query.get_or_raise(software_id)
        return [ssa.server.to_json() for ssa in soft.ssas]

    # @forward_or_dispatch()
    # @jwt_required
    # @securizer
    # @validate_schema(software_servers_put)
    # @lock_catalog
    # def put(self, software_id):
    #     json = request.get_json()
    #
    #     soft = Software.query.get_or_raise(software_id)
    #
    #     # delete all associations
    #     soft.ssas = []
    #
    #     for ssa_json in json:
    #         server = Server.query.get_or_raise(ssa_json['server_id'])
    #         ssa = SoftwareServerAssociation(software=soft, server=server, path=ssa_json['path'])
    #         db.session.add(ssa)
    #
    #     db.session.commit()
    #     return

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(software_patch)
    @lock_catalog
    def patch(self, software_id):
        json = request.get_json()

        soft = Software.query.get_or_raise(software_id)
        server = Server.query.get_or_raise(json['server_id'])

        ssa = set_software_server(soft, server, json['path'], recalculate_data=json.get('recalculate_data', False))
        db.session.add(ssa)
        db.session.commit()
        return {}, 204
