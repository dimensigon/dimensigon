from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.domain.entities import ActionTemplate, ActionType
from dm.web import db
from dm.web.decorators import securizer, forward_or_dispatch, validate_schema
from dm.web.helpers import filter_query
from dm.web.json_schemas import post_action_template_schema


class ActionTemplateList(Resource):

    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(ActionTemplate, request.args)
        return [at.to_json() for at in query.all()]

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(post_action_template_schema)
    def post(self):
        json_data = request.get_json()
        json_data['action_type'] = ActionType[json_data['action_type']]
        at = ActionTemplate(**json_data)
        db.session.add(at)
        db.session.commit()
        return {'action_template_id': str(at.id)}, 201


class ActionTemplateResource(Resource):
    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self, action_template_id):
        return ActionTemplate.query.get_or_404(action_template_id).to_json()
