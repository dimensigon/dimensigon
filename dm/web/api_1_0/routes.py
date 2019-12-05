from flask import request
from flask_jwt_extended import jwt_required

from dm.web import catalog_manager as cm, interactor, repo_manager as repo
from dm.utils.decorators import securizer, forward_or_dispatch
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


@api_bp.route('/join', methods=['POST'])
@jwt_required
@securizer
def join():
    dim = repo.DimensionRepo.get_by_public_key()
    return dim


@api_bp.route('/catalog/<string:data_mark>', methods=['GET', 'POST'])
@securizer
@jwt_required
@forward_or_dispatch
def catalog(data_mark):
    try:
        data_validated = interactor.catalog.to_type(data_mark)
    except Exception as e:
        return {'error': f'Invalid Data Mark: {e}'}, 400
    data = interactor.mediator.local_get_delta_catalog(data_validated)
    return data
