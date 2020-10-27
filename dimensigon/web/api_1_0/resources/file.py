import base64
import logging
import os
import zlib

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_restful import Resource

from dimensigon.domain.entities import Server, File, FileServerAssociation
from dimensigon.web import db, errors
from dimensigon.web.decorators import forward_or_dispatch, securizer, validate_schema, lock_catalog
from dimensigon.web.helpers import filter_query, check_param_in_uri
from dimensigon.web.json_schemas import files_post, file_post, file_patch


class FileList(Resource):

    @securizer
    @jwt_required
    @forward_or_dispatch()
    def get(self):
        query = filter_query(File, request.args)
        return [file.to_json(human=check_param_in_uri('human'), delete_data=False, destinations=True) for file in
                query.all()]

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(files_post)
    @lock_catalog
    def post(self):
        data = request.get_json()
        source_server = Server.query.get_or_raise(data.pop('src_server_id'))
        entities = [File(source_server=source_server, target=data['target'], dest_folder=data.get('dest_folder', None))]
        for dest in data.get('destinations', []):
            dest_server = Server.query_class.get_or_raise(dest['dst_server_id'])
            entities.append(FileServerAssociation(file=entities[0], destination_server=dest_server,
                                                  dest_folder=dest.get('dest_folder', None)))
        db.session.add_all(entities)
        db.session.commit()
        return {'id': str(entities[0].id)}, 201


class FileResource(Resource):

    @securizer
    @jwt_required
    @forward_or_dispatch()
    def get(self, file_id):
        return File.query.get_or_raise(file_id).to_json(human=check_param_in_uri('human'), delete_data=False,
                                                        destinations=True)

    @securizer
    @jwt_required
    @forward_or_dispatch()
    @validate_schema(file_post)
    def post(self, file_id):
        if get_jwt_identity() == '00000000-0000-0000-0000-000000000001':
            data = request.get_json()
            file = File.query.get(file_id)
            if file is None and not data.get('force', False):
                raise errors.EntityNotFound("File", file_id)

            file = data.get('file')
            content = zlib.decompress(base64.b64decode(data.get('data').encode('ascii')))
            _logger = logging.getLogger('dimensigon.fileSync')
            _logger.debug(f"syncing file {file}")
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

    @securizer
    @jwt_required
    @forward_or_dispatch()
    @validate_schema(file_patch)
    @lock_catalog
    def patch(self, file_id):
        file = File.query.get_or_raise(file_id)
        data = request.get_json()
        if 'src_server_id' in data and file.source_server.id != data['src_server_id']:
            s = Server.query.get_or_raise(data['src_server_id'])
            file.source_server = s
        if 'target' in data and file.target != data['target']:
            if not data['target']:
                raise errors.InvalidValue("The field cannot be empty", field='target', value=data['target'])
            file.target = data['target']
        if 'dest_folder' in data and file.dest_folder != data.get('dest_folder'):
            file.dest_folder = data.get('dest_folder')
        if 'destinations' in data:
            current = set([d.dst_server_id for d in file.destinations])
            new = set([d.get('dst_server_id') for d in data['destinations']])
            to_remove = current - new
            to_modify = new.intersection(current)
            to_add = new - current
            for dst_server_id in to_remove:
                dest = [d for d in file.destinations if d.dst_server_id == dst_server_id][0]
                file.destinations.remove(dest)
            for dst_server_id in to_modify:
                curr_dest = [d for d in file.destinations if d.dst_server_id == dst_server_id][0]
                in_dest = [d for d in data.get('destinations') if d['dst_server_id'] == dst_server_id][0]
                if curr_dest.dest_folder != in_dest.get('dest_folder', None):
                    curr_dest.dest_folder = in_dest.get('dest_folder', None)
            for dst_server_id in to_add:
                dest = [d for d in data.get('destinations') if d['dst_server_id'] == dst_server_id][0]
                s = Server.query.get_or_raise(dest.get('dst_server_id'))
                fsa = FileServerAssociation(file=file, destination_server=s, dest_folder=dest.get('dest_folder', None))
                db.session.add(fsa)
        if file in db.session.dirty:
            db.session.commit()
            return {}, 204
        return {}, 202

    @securizer
    @jwt_required
    @forward_or_dispatch()
    @lock_catalog
    def delete(self, file_id):
        file = File.query.get_or_raise(file_id)
        file.delete()
        db.session.commit()
        return {}, 204
