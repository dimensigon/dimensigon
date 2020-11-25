from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import ActionTemplate, ActionType
from dimensigon.web import db
from dimensigon.web.decorators import securizer, forward_or_dispatch, validate_schema, lock_catalog
from dimensigon.web.helpers import filter_query, check_param_in_uri
from dimensigon.web.json_schemas import action_template_patch, action_template_post


class ActionTemplateList(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(ActionTemplate, request.args)
        return [at.to_json(split_lines=check_param_in_uri('split_lines')) for at in query.all()]

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(action_template_post)
    @lock_catalog
    def post(self):
        json_data = request.get_json()
        if isinstance(json_data, dict):
            json_data = [json_data]
        resp_data = []
        for json_at in json_data:
            json_at['action_type'] = ActionType[json_at['action_type']]
            if 'version' not in json_at:
                json_at['version'] = ActionTemplate.query.filter_by(name=json_at['name']).count() + 1
            at = ActionTemplate(**json_at)
            db.session.add(at)
            data = {'id': at.id}
            if 'version' not in json_at:
                data.update(version=at.version)
            resp_data.append(data)
        db.session.commit()
        return resp_data[0] if isinstance(request.get_json(), dict) else resp_data, 201


class ActionTemplateResource(Resource):
    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self, action_template_id):
        return ActionTemplate.query.get_or_raise(action_template_id).to_json(
            split_lines=check_param_in_uri('split_lines'))

    @jwt_required
    @securizer
    @forward_or_dispatch()
    @validate_schema(action_template_patch)
    @lock_catalog
    def patch(self, action_template_id):
        at = ActionTemplate.query.get_or_raise(action_template_id)
        data = request.get_json()
        if 'action_type' in data and at.action_type != ActionType[data.get('action_type')]:
            at.action_type = ActionType[data.get('action_type')]
        if 'code' in data and at.code != (data.get('code')):
            aux = data.get('code')
            at.code = aux if isinstance(aux, str) else '\n'.join(aux)
        if 'parameters' in data and at.parameters != data.get('parameters'):
            at.parameters = data.get('parameters')
        if 'expected_stdout' in data and at.expected_stdout != data.get('expected_stdout'):
            aux = data.get('expected_stdout')
            at.expected_stdout = aux if isinstance(aux, str) else '\n'.join(aux)
        if 'expected_stderr' in data and at.expected_stderr != data.get('expected_stderr'):
            aux = data.get('expected_stderr')
            at.expected_stderr = aux if isinstance(aux, str) else '\n'.join(aux)
        if 'expected_rc' in data and at.expected_rc != data.get('expected_rc'):
            at.expected_rc = data.get('expected_rc')
        if 'pre_process' in data and at.pre_process != data.get('pre_process'):
            aux = data.get('pre_process')
            at.pre_process = aux if isinstance(aux, str) else '\n'.join(aux)
        if 'post_process' in data and at.post_process != data.get('post_process'):
            aux = data.get('post_process')
            at.post_process = aux if isinstance(aux, str) else '\n'.join(aux)
        if 'description' in data and at.description != data.get('description'):
            aux = data.get('description')
            at.description = aux if isinstance(aux, str) else '\n'.join(aux)
        if at in db.session.dirty:
            db.session.commit()
            return {}, 204
        return {}, 202
