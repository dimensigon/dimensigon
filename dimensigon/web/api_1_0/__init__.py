from flask import Blueprint
from flask_restful import Api

api_bp = Blueprint('api_1_0', __name__, url_prefix='/api/v1.0')
api = Api(api_bp)

# import routes
import dimensigon.web.api_1_0.urls.locker
import dimensigon.web.api_1_0.resources.transfer
import dimensigon.web.api_1_0.urls.use_cases

from dimensigon.web.api_1_0.resources import *

# generate resources Flask_Restful
api.add_resource(ActionTemplateList, '/action_templates')
api.add_resource(ActionTemplateResource, '/action_templates/<action_template_id>')

api.add_resource(LogList, '/log')
api.add_resource(LogResource, '/log/<log_id>')

api.add_resource(FileList, '/file')
api.add_resource(FileResource, '/file/<file_id>')

api.add_resource(FileServerAssociationList, '/file/<file_id>/destinations')

api.add_resource(OrchestrationList, '/orchestrations')
api.add_resource(OrchestrationResource, '/orchestrations/<orchestration_id>')
api.add_resource(OrchestrationExecutionRelationship, '/orchestrations/<orchestration_id>/executions')

api.add_resource(OrchExecutionList, '/orchestration_executions')
api.add_resource(OrchExecutionResource, '/orchestration_executions/<execution_id>')
api.add_resource(OrchExecStepExecRelationship, '/orchestration_executions/<execution_id>/step_executions')

api.add_resource(ServerList, '/servers')
api.add_resource(ServerResource, '/servers/<server_id>')
api.add_resource(GranuleList, '/granules')

api.add_resource(SoftwareList, '/software')
api.add_resource(SoftwareResource, '/software/<software_id>')
api.add_resource(SoftwareServersResource, '/software/<software_id>/servers')

api.add_resource(StepList, '/steps')
api.add_resource(StepResource, '/steps/<step_id>')
api.add_resource(StepRelationshipParents, '/steps/<step_id>/relationship/parents')
api.add_resource(StepRelationshipChildren, '/steps/<step_id>/relationship/children')

api.add_resource(StepExecutionList, '/step_executions')
api.add_resource(StepExecutionResource, '/step_executions/<execution_id>')

api.add_resource(TransferList, '/transfers')
api.add_resource(TransferResource, '/transfers/<transfer_id>')

api.add_resource(UserList, '/users')
api.add_resource(UserResource, '/users/<user_id>')

api.add_resource(VaultList, '/vault')
api.add_resource(VaultResource, '/vault/<scope>/<name>', '/vault/<name>')
