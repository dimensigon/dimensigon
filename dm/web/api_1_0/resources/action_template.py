import jsonschema
from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.domain.entities import ActionTemplate, ActionType
from dm.web import db
from dm.web.decorators import securizer, forward_or_dispatch
from dm.web.helpers import filter_query
from dm.web.json_schemas import post_action_template_schema


class ActionTemplateList(Resource):

    @securizer
    @jwt_required
    @forward_or_dispatch
    def get(self):
        query = filter_query(ActionTemplate, request.args)
        return [at.to_json() for at in query.all()]

    @securizer
    @jwt_required
    @forward_or_dispatch
    def post(self):
        json_data = request.get_json()
        jsonschema.validate(json_data, post_action_template_schema)
        json_data['action_type'] = ActionType[json_data['action_type']]
        at = ActionTemplate(**json_data)
        db.session.add(at)
        db.session.commit()
        return {'action_template_id': str(at.id)}, 201


class ActionTemplateResource(Resource):
    @securizer
    @jwt_required
    @forward_or_dispatch
    def get(self, action_template_id):
        return ActionTemplate.query.get_or_404(action_template_id).to_json()
