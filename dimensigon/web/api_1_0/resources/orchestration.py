from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import Orchestration
from dimensigon.utils.helpers import is_iterable_not_string
from dimensigon.web import db
from dimensigon.web.decorators import securizer, forward_or_dispatch, validate_schema, lock_catalog
from dimensigon.web.helpers import filter_query, check_param_in_uri
from dimensigon.web.json_schemas import orchestration_post, orchestration_patch


class OrchestrationList(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(Orchestration, request.args).order_by(Orchestration.created_at)
        return [o.to_json(add_target=check_param_in_uri('target'), add_params=check_param_in_uri('vars'),
                          add_steps=check_param_in_uri('steps'), add_action=check_param_in_uri('action'),
                          split_lines=check_param_in_uri('split_lines'), add_schema=check_param_in_uri('schema')) for o
                in query.all()]

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(orchestration_post)
    @lock_catalog
    def post(self):
        json_data = request.get_json()
        generated_version = False
        if 'version' not in json_data:
            generated_version = True
            json_data['version'] = Orchestration.query.filter_by(name=json_data['name']).count() + 1
        o = Orchestration(**json_data)
        db.session.add(o)
        db.session.commit()
        resp_data = {'id': str(o.id)}
        if generated_version:
            resp_data.update(version=o.version)
        return resp_data, 201


class OrchestrationResource(Resource):
    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self, orchestration_id):
        return Orchestration.query.get_or_raise(orchestration_id).to_json(check_param_in_uri('target'),
                                                                          add_schema=check_param_in_uri('schema'),
                                                                          split_lines=check_param_in_uri('split_lines'))

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(orchestration_patch)
    @lock_catalog
    def patch(self, orchestration_id):
        o = Orchestration.query.get_or_raise(orchestration_id)
        for k, v in request.get_json().items():
            if k == 'description':
                v = '\n'.join(v) if is_iterable_not_string(v) else v
            setattr(o, k, v)
        db.session.commit()
        return {}, 204
