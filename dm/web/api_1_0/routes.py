from dm.web.api_1_0 import api, api_bp
from dm.web.api_1_0.resources import ActionTemplateListResource, ActionTemplateResource, StepListResource, \
    OrchestrationListResource, OrchestrationResource, ServerListResource, ServiceListResource, ServerResource, \
    ServiceResource, StepResource

api.add_resource(ActionTemplateListResource, '/action_templates', endpoint='action_template_list')
api.add_resource(ActionTemplateResource, '/action_template/<id>', endpoint='action_template')
api.add_resource(StepListResource, '/steps', endpoint='step_list')
api.add_resource(StepResource, '/step/<id>', endpoint='step')
api.add_resource(OrchestrationListResource, '/orchestrations', endpoint='orchestration_list')
api.add_resource(OrchestrationResource, '/orchestration/<id>', endpoint='orchestration')
api.add_resource(ServerListResource, '/servers', endpoint='server_list')
api.add_resource(ServerResource, '/server/<id>', endpoint='server')
api.add_resource(ServiceListResource, '/services', endpoint='service_list')
api.add_resource(ServiceResource, '/service/<id>', endpoint='service')


@api_bp.route('/')
def home():
    return "API v1.0 documentation page"
