from flask import Blueprint
from flask_restful import Api

api_bp = Blueprint('api_1_0', __name__, url_prefix='/api/v1.0')
api = Api(api_bp)

# import routes
import dm.web.api_1_0.routes
import dm.web.api_1_0.urls.transfer
import dm.web.api_1_0.urls.use_cases

from dm.web.api_1_0.resources import *

# generate resources Flask_Restful
api.add_resource(SoftwareList, '/software')
api.add_resource(SoftwareResource, '/software/<software_id>')
api.add_resource(SoftwareServers, '/software/<software_id>/server')

api.add_resource(JobList, '/jobs')
api.add_resource(JobResource, '/jobs/<job_id>')
