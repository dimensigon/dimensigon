from flask import Blueprint, jsonify, request

import dm
from dm.network.gateway import dispatch_message
from dm.utils.decorators import forward_or_dispatch, securizer
from dm.web import catalog_manager as cm, interactor
from elevator import __version__ as elevator_ver

blueprint_name = 'root'
root_bp = Blueprint(blueprint_name, __name__)


@root_bp.route('/healthcheck', methods=['GET'])
def healthcheck():
    catalog_ver = cm.max_data_mark
    if catalog_ver:
        catalog_ver = cm.max_data_mark.strftime(cm.format)

    return jsonify({"version": dm.__version__,
                    "elevator_version": elevator_ver,
                    "catalog_version": catalog_ver,

                    "neighbours": [],
                    "services": [
                        {
                            "service1": {
                                "status": "ALIVE"
                            }
                        }
                    ]
                    })


@root_bp.route('/socket', methods=['POST'])
@securizer
@forward_or_dispatch
def socket():
    data = request.get_json()
    return dispatch_message(data, interactor._mediator)




