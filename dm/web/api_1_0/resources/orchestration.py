from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.domain.entities import Orchestration
from dm.web import db
from dm.web.decorators import securizer, forward_or_dispatch, validate_schema, lock_catalog
from dm.web.helpers import filter_query
from dm.web.json_schemas import orchestration_post, orchestration_patch


class OrchestrationResourceList(Resource):

    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(Orchestration, request.args)
        return [o.to_json() for o in query.all()]

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(orchestration_post)
    @lock_catalog
    def post(self):
        json_data = request.get_json()
        o = Orchestration(**json_data)
        db.session.add(o)
        db.session.commit()
        return {'orchestration_id': str(o.id)}, 201


class OrchestrationResource(Resource):
    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self, orchestration_id):
        return Orchestration.query.get_or_404(orchestration_id).to_json()

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(orchestration_patch)
    @lock_catalog
    def patch(self, orchestration_id):
        o = Orchestration.query.get_or_404(orchestration_id)
        for k, v in request.get_json().items():
            setattr(o, k, v)
        db.session.commit()
        return {}, 204