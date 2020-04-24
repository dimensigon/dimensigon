from flask import Blueprint
from flask_restful import Api

api_bp = Blueprint('api_1_0', __name__, url_prefix='/api/v1.0')
api = Api(api_bp)

# import routes
import dm.web.api_1_0.urls.locker
import dm.web.api_1_0.urls.transfer
import dm.web.api_1_0.urls.use_cases

from dm.web.api_1_0.resources import *

# generate resources Flask_Restful
api.add_resource(ActionTemplateList, '/action_template')
api.add_resource(ActionTemplateResource, '/action_template/<action_template_id>')

api.add_resource(SoftwareList, '/software')
api.add_resource(SoftwareResource, '/software/<software_id>')
api.add_resource(SoftwareServers, '/software/<software_id>/server')

api.add_resource(LogResourceList, '/log')
api.add_resource(LogResource, '/log/<log_id>')

api.add_resource(UserResourceList, '/user')
api.add_resource(UserResource, '/user/<user_id>')

api.add_resource(OrchestrationResourceList, '/orchestration')
api.add_resource(OrchestrationResource, '/orchestration/<orchestration_id>')

api.add_resource(StepResourceList, '/step')
api.add_resource(StepResource, '/step/<step_id>')

api.add_resource(StepRelationshipParentsResource, '/step/<step_id>/relationship/parents')
api.add_resource(StepRelationshipChildrenResource, '/step/<step_id>/relationship/children')
