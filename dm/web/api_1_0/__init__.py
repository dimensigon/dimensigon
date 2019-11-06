from flask import Blueprint
from flask_restful import Api

api_bp = Blueprint('api_1_0', __name__, url_prefix='/api/v1.0')
api = Api(api_bp)

import dm.web.api_1_0.routes
