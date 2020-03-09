import os
import signal
from functools import partial

import jsonschema
from flask import Blueprint, request, current_app

import dm
from dm import defaults
from dm.domain import entities
from dm.domain.entities import Server
from dm.web import db
from dm.web.decorators import forward_or_dispatch, securizer
from dm.web.json_schemas import schema_healthcheck
from elevator import __version__ as elevator_ver

blueprint_name = 'root'
root_bp = Blueprint(blueprint_name, __name__)


@root_bp.route('/')
def home():
    return {'message': 'Welcome to dimensigon'}


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        func = partial(os.kill, os.getppid(), signal.SIGTERM)
    current_app.logger.info('Shutting down server')
    current_app.scheduler.shutdown()
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


@root_bp.route('/healthcheck', methods=['GET', 'POST'])
@forward_or_dispatch
@securizer
def healthcheck():
    if request.method == 'GET':
        # catalog_ver = current_app.catalog_manager.max_data_mark
        # if catalog_ver:
        #     catalog_ver = current_app.catalog_manager.max_data_mark.strftime(current_app.catalog_manager.format)
        catalog_ver = db.session.query(db.func.max(entities.Catalog.last_modified_at)).scalar()
        return {"version": dm.__version__,
                "elevator_version": elevator_ver,
                "catalog_version": catalog_ver.strftime(defaults.DATEMARK_FORMAT) if catalog_ver else None,
                "scheduler": "running" if getattr(getattr(current_app, 'scheduler', None), 'running',
                                                  None) else "stopped",
                "neighbours": [str(server.id) for server in Server.get_neighbours()],
                "services": []
                }
    elif request.method == 'POST':
        data = request.json
        jsonschema.validate(data, schema_healthcheck)

        if data.get('action') == 'stop':
            shutdown_server()
            return '', 202
        elif data.get('action') == 'restart':
            return {'message': 'restart is not implemented'}, 500


@root_bp.route('/ping', methods=['POST'])
@forward_or_dispatch
def ping():
    resp = request.get_json()
    return resp
