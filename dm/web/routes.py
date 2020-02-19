import os
import signal
from functools import partial

import jsonschema
from flask import Blueprint, jsonify, request, current_app

import dm
from dm import db
from dm.domain import entities
from dm.domain.entities import Server
from dm.scheduler import scheduler
from dm.web.decorators import forward_or_dispatch
from elevator import __version__ as elevator_ver

blueprint_name = 'root'
root_bp = Blueprint(blueprint_name, __name__)


@root_bp.route('/')
def home():
    return {'message': 'Welcome to dimensigon'}


schema_healthcheck = {
    "type": "object",
    "properties": {
        "action": {"type": "string",
                   "pattern": "^(reboot|stop)"},
    },
    "required": ["action"]
}


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        func = partial(os.kill, os.getppid(), signal.SIGTERM)
    current_app.logger.info('Shutting down server')
    scheduler.shutdown()
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


@root_bp.route('/healthcheck', methods=['GET', 'POST'])
@forward_or_dispatch
def healthcheck():
    if request.method == 'GET':
        # catalog_ver = current_app.catalog_manager.max_data_mark
        # if catalog_ver:
        #     catalog_ver = current_app.catalog_manager.max_data_mark.strftime(current_app.catalog_manager.format)
        catalog_ver = db.session.query(db.func.max(entities.Catalog.last_modified_at)).scalar()
        return jsonify({"version": dm.__version__,
                        "elevator_version": elevator_ver,
                        "catalog_version": catalog_ver.strftime("%Y%m%d%H%M%S%f"),
                        "scheduler": "running" if scheduler.running else "stopped",
                        "neighbours": [str(server.id) for server in Server.get_neighbours()],
                        "services": []
                        })
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
