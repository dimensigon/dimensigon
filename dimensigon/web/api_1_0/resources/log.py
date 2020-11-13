import base64
import os
import zlib

from flask import request, current_app
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon import defaults
from dimensigon.domain.entities import Log, Server
from dimensigon.domain.entities.log import Mode
from dimensigon.utils.helpers import clean_string
from dimensigon.web import db, errors
from dimensigon.web.decorators import forward_or_dispatch, securizer, validate_schema, lock_catalog
from dimensigon.web.helpers import filter_query, check_param_in_uri
from dimensigon.web.json_schemas import log_post, logs_post, log_patch


class LogList(Resource):

    @jwt_required
    @securizer
    @forward_or_dispatch()
    def get(self):
        query = filter_query(Log, request.args)
        return [log.to_json(human=check_param_in_uri('human'), delete_data=False) for log in query.all()]

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(logs_post)
    @lock_catalog
    def post(self):
        data = request.get_json()
        source_server = Server.query.get_or_raise(data.pop('src_server_id'))
        destination_server = Server.query.get_or_raise(data.pop('dst_server_id'))
        if source_server == destination_server:
            return {'error': 'source and destination must be different'}, 400
        if 'mode' in data:
            data['mode'] = Mode[data['mode']]
            if data['mode'] == Mode.FOLDER:
                if 'dest_folder' not in data:
                    raise errors.ParameterMustBeSet("property 'dest_folder' must be set when mode=FOLDER")
        log = Log(source_server=source_server, destination_server=destination_server, **data)
        db.session.add(log)
        db.session.commit()
        return {'id': str(log.id)}, 201


class LogResource(Resource):

    @jwt_required
    @securizer
    @forward_or_dispatch()
    def get(self, log_id):
        return Log.query.get_or_raise(log_id).to_json()

    @jwt_required
    @securizer
    @forward_or_dispatch()
    @validate_schema(log_post)
    def post(self, log_id):
        log = Log.query.get_or_raise(log_id)
        data = request.get_json()
        file = data.get('file')
        if log.mode in (Mode.REPO_MIRROR, Mode.REPO_ROOT):
            file = file.format(
                LOG_REPO=os.path.join(current_app.dm.config.config_dir, defaults.LOG_SENDER_REPO,
                                      clean_string(log.source_server.name)))
        if data.get('compress', False):
            data_log = zlib.decompress(base64.b64decode(data.get('data').encode('ascii')))
        else:
            data_log = base64.b64decode(data.get('data').encode('ascii'))

        if not os.path.exists(os.path.dirname(file)):
            try:
                os.makedirs(os.path.dirname(file))
            except PermissionError:
                raise errors.GenericError(f"Permission denied creating '{os.path.dirname(file)}'", 500)
        try:
            with open(file, 'ab') as fh:
                fh.write(data_log)
        except Exception as e:
            raise errors.GenericError(f"{e}", 500)

        return {'offset': os.path.getsize(file)}

    @jwt_required
    @securizer
    @forward_or_dispatch()
    @validate_schema(log_patch)
    @lock_catalog
    def patch(self, log_id):
        log = Log.query.get_or_raise(log_id)
        data = request.get_json()
        if 'include' in data and log.include != data.get('include'):
            log.include = data.get('include')
        if 'exclude' in data and log.exclude != (data.get('exclude') or '^$'):
            log.exclude = data.get('exclude')
        if 'recursive' in data and log.recursive != data.get('recursive'):
            log.recursive = data.get('recursive')
        if 'mode' in data and log.mode != data.get('mode'):
            log.mode = data.get('mode')
        if log.mode == Mode.FOLDER:
            if 'dest_folder' in data and log.dest_folder != data.get('dest_folder'):
                log.dest_folder = data.get('dest_folder')
            if log.dest_folder == None:
                raise errors.ParameterMustBeSet("property 'dest_folder' must be set when mode=FOLDER")
        if log in db.session.dirty:
            db.session.commit()
            return {}, 204
        return {}, 202

    @jwt_required
    @securizer
    @forward_or_dispatch()
    @lock_catalog
    def delete(self, log_id):
        log = Log.query.get_or_raise(log_id)
        log.delete()
        db.session.commit()
        return {}, 204
