import base64
import os

from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.domain.entities import Log, Server
from dm.web import db
from dm.web.decorators import forward_or_dispatch, securizer, validate_schema, lock_catalog
from dm.web.helpers import filter_query
from dm.web.json_schemas import schema_post_log, schema_create_log, schema_patch_log


class LogResourceList(Resource):

    @securizer
    @jwt_required
    @forward_or_dispatch
    def get(self):
        query = filter_query(Log, request.args)
        return [soft.to_json() for soft in query.all()]

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(schema_create_log)
    @lock_catalog
    def post(self):
        data = request.get_json()
        source_server = Server.query.get_or_404(data.pop('src_server_id'))
        destination_server = Server.query.get_or_404(data.pop('dst_server_id'))
        if source_server == destination_server:
            return {'error': 'source and destination must be different'}, 400
        log = Log(source_server=source_server, destination_server=destination_server, **data)
        db.session.add(log)
        db.session.commit()
        return {'log_id': str(log.id)}, 201


class LogResource(Resource):

    @securizer
    @jwt_required
    @forward_or_dispatch
    def get(self, log_id):
        return Log.query.get_or_404(log_id).to_json()

    @securizer
    @jwt_required
    @forward_or_dispatch
    @validate_schema(schema_post_log)
    def post(self, log_id):
        log = Log.query.get_or_404(log_id)
        data = request.get_json()
        file = data.get('file')
        data_log = base64.b64decode(data.get('data').encode('ascii'))
        try:
            if not os.path.exists(os.path.dirname(file)):
                os.makedirs(os.path.dirname(file))
            with open(file, 'ab') as fh:
                fh.write(data_log)
        except Exception as e:
            return {"error": str(e)}
        return {'offset': os.path.getsize(file)}

    @securizer
    @jwt_required
    @forward_or_dispatch
    @validate_schema(schema_patch_log)
    @lock_catalog
    def patch(self, log_id):
        log = Log.query.get_or_404(log_id)
        data = request.get_json()
        if 'include' in data and log.include != data.get('include'):
            log.include = data.get('include')
        if 'exclude' in data and log.exclude != (data.get('exclude') or '^$'):
            log.exclude = data.get('exclude')
        if 'recursive' in data and log.recursive != data.get('recursive'):
            log.recursive = data.get('recursive')
        if 'dest_folder' in data and log.dest_folder != data.get('dest_folder'):
            log.dest_folder = data.get('dest_folder')
        if log in db.session.dirty:
            db.session.commit()
            return {}, 204
        return {}, 202

    # @securizer
    # @jwt_required
    # @forward_or_dispatch
    # def delete(self, log_id):
    #     log = Log.query.get_or_404(log_id)
    #     db.session.delete(log)
    #     db.session.commit()
    #     return {}, 204
