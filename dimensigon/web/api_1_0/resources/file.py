import base64
import logging
import os
import zlib

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_restful import Resource

from dimensigon.domain.entities import Server, File, FileServerAssociation
from dimensigon.web import db, errors
from dimensigon.web.api_1_0 import api_bp
from dimensigon.web.decorators import forward_or_dispatch, securizer, validate_schema, lock_catalog
from dimensigon.web.helpers import filter_query, check_param_in_uri, get_or_raise
from dimensigon.web.json_schemas import files_post, file_post, file_patch, file_sync

_logger = logging.getLogger('dm.fileSync')


@api_bp.route("/file/<file_id>/sync", methods=['POST'])
@jwt_required()
@securizer
@forward_or_dispatch()
@validate_schema(file_sync)
def file_sync(file_id):
    if get_jwt_identity() == '00000000-0000-0000-0000-000000000001':
        data = request.get_json()
        file = db.session.get(File, file_id)
        if file is None and not data.get('force', False):
            raise errors.EntityNotFound("File", file_id)

        file = data.get('file')
        content = zlib.decompress(base64.b64decode(data.get('data').encode('ascii')))

        _logger.debug(f"received file sync {file}.")
        try:
            if not os.path.exists(os.path.dirname(file)):
                os.makedirs(os.path.dirname(file))
            with open(file, 'wb') as fh:
                fh.write(content)
        except Exception as e:
            raise errors.GenericError(f"Error while trying to create/write file: {e}", 500)
        return {}, 204
    else:
        raise errors.UserForbiddenError


class FileList(Resource):

    @jwt_required()
    @securizer
    @forward_or_dispatch()
    def get(self):
        stmt = filter_query(File, request.args)
        return [file.to_json(human=check_param_in_uri('human'), no_delete=True,
                             destinations=check_param_in_uri('destinations')) for file in
                db.session.execute(stmt).scalars().all()]

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @validate_schema(files_post)
    @lock_catalog
    def post(self):
        data = request.get_json()
        source_server = get_or_raise(Server, data.pop('src_server_id'))
        entities = [File(source_server=source_server, target=data['target'], dest_folder=data.get('dest_folder', None))]
        for dest in data.get('destinations', []):
            dest_server = get_or_raise(Server, dest['dst_server_id'])
            entities.append(FileServerAssociation(file=entities[0], destination_server=dest_server,
                                                  dest_folder=dest.get('dest_folder', None)))
        db.session.add_all(entities)
        db.session.commit()
        return {'id': str(entities[0].id)}, 201


class FileResource(Resource):

    @jwt_required()
    @securizer
    @forward_or_dispatch()
    def get(self, file_id):
        return get_or_raise(File, file_id).to_json(human=check_param_in_uri('human'), delete_data=False,
                                                        destinations=True)

    @jwt_required()
    @securizer
    @forward_or_dispatch()
    @validate_schema(file_post)
    def post(self, file_id):
        from .file_server_association import change_destinations
        file = get_or_raise(File, file_id)
        data = request.get_json()
        file.source_server = get_or_raise(Server, data.get('src_server_id'))
        if not data['target']:
            raise errors.InvalidValue("The field cannot be empty", field='target', value=data['target'])
        file.target = data.get('target')
        file.dest_folder = data.get('dest_folder')
        change_destinations(file, data.get('destinations', []))
        if file in db.session.dirty:
            db.session.commit()
            return {}, 204
        return {}, 202

    @jwt_required()
    @securizer
    @forward_or_dispatch()
    @validate_schema(file_patch)
    @lock_catalog
    def patch(self, file_id):
        from .file_server_association import change_destinations
        file = get_or_raise(File, file_id)
        data = request.get_json()
        if 'src_server_id' in data and file.source_server.id != data['src_server_id']:
            s = get_or_raise(Server, data['src_server_id'])
            file.source_server = s
        if 'target' in data and file.target != data['target']:
            if not data['target']:
                raise errors.InvalidValue("The field cannot be empty", field='target', value=data['target'])
            file.target = data['target']
        if 'dest_folder' in data and file.dest_folder != data.get('dest_folder'):
            file.dest_folder = data.get('dest_folder')
        if 'destinations' in data:
            change_destinations(file, data['destinations'])
        if file in db.session.dirty:
            db.session.commit()
            return {}, 204
        return {}, 202

    @jwt_required()
    @securizer
    @forward_or_dispatch()
    @lock_catalog
    def delete(self, file_id):
        file = get_or_raise(File, file_id)
        file.delete()
        db.session.commit()
        return {}, 204
