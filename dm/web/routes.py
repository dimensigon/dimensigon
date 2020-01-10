from datetime import datetime

from flask import Blueprint, jsonify, current_app, request
from sqlalchemy import func

import dm
from dm.domain import entities
# from dm.domain.entities.catalog import Catalog
from dm.web.decorators import forward_or_dispatch
from dm.web import db
from elevator import __version__ as elevator_ver

blueprint_name = 'root'
root_bp = Blueprint(blueprint_name, __name__)


@root_bp.route('/healthcheck', methods=['GET', 'POST'])
@forward_or_dispatch
def healthcheck():
    # catalog_ver = current_app.catalog_manager.max_data_mark
    # if catalog_ver:
    #     catalog_ver = current_app.catalog_manager.max_data_mark.strftime(current_app.catalog_manager.format)
    catalog_ver = db.session.query(db.func.max(entities.Catalog.last_modified_at)).scalar()
    return jsonify({"version": dm.__version__,
                    "elevator_version": elevator_ver,
                    "catalog_version": catalog_ver.strftime("%Y%m%d%H%M%S%f"),

                    "neighbours": [],
                    "services": [
                        {
                            "service1": {
                                "status": "ALIVE"
                            }
                        }
                    ]
                    })


@root_bp.route('/ping', methods=['POST'])
@forward_or_dispatch
def ping():
    resp = request.get_json()
    return resp
