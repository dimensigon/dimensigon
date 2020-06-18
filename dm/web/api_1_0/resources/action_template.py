from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.domain.entities import ActionTemplate, ActionType
from dm.web import db
from dm.web.decorators import securizer, forward_or_dispatch, validate_schema, lock_catalog
from dm.web.helpers import filter_query
from dm.web.json_schemas import action_template_patch, action_template_post


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
    @validate_schema(action_template_post)
    @lock_catalog
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

    @securizer
    @jwt_required
    @forward_or_dispatch
    @validate_schema(action_template_patch)
    @lock_catalog
    def patch(self, action_template_id):
        at = ActionTemplate.query.get_or_404(action_template_id)
        data = request.get_json()
        if 'action_type' in data and at.action_type != ActionType[data.get('action_type')]:
            at.action_type = ActionType[data.get('action_type')]
        if 'code' in data and at.code != (data.get('code')):
            at.code = data.get('code')
        if 'parameters' in data and at.parameters != data.get('parameters'):
            at.parameters = data.get('parameters')
        if 'expected_stdout' in data and at.expected_stdout != data.get('expected_stdout'):
            at.expected_stdout = data.get('expected_stdout')
        if 'expected_stderr' in data and at.expected_stderr != data.get('expected_stderr'):
            at.expected_stderr = data.get('expected_stderr')
        if 'expected_rc' in data and at.expected_rc != data.get('expected_rc'):
            at.expected_rc = data.get('expected_rc')
        if 'pre_process' in data and at.pre_process != data.get('pre_process'):
            at.pre_process = data.get('pre_process')
        if 'post_process' in data and at.post_process != data.get('post_process'):
            at.post_process = data.get('post_process')
        if at in db.session.dirty:
            db.session.commit()
            return {}, 204
        return {}, 202
