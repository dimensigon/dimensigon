from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import Step
from dimensigon.web import db
from dimensigon.web.decorators import forward_or_dispatch, securizer, validate_schema, lock_catalog
from dimensigon.web.json_schemas import step_parents


class StepRelationshipParents(Resource):
    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self, step_id):
        s: Step = Step.query.get_or_raise(step_id)
        return dict(parent_step_ids=[str(ps.id) for ps in s.parents]), 200

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(step_parents)
    @lock_catalog
    def patch(self, step_id):
        s: Step = Step.query.get_or_raise(step_id)
        parent_step_ids = request.get_json()['parent_step_ids']
        parent_steps = []
        for parent_step_id in parent_step_ids:
            parent_steps.append(Step.query.get_or_raise(parent_step_id))
        s.orchestration.set_parents(s, parent_steps)

        db.session.commit()

        return dict(parent_step_ids=[str(ps.id) for ps in s.parents]), 200

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(step_parents)
    @lock_catalog
    def post(self, step_id):
        s = Step.query.get_or_raise(step_id)
        parent_step_ids = request.get_json()['parent_step_ids']
        parent_steps = []
        for parent_step_id in parent_step_ids:
            parent_steps.append(Step.query.get_or_raise(parent_step_id))
        s.orchestration.add_parents(s, parent_steps)

        db.session.commit()

        return dict(parent_step_ids=[str(ps.id) for ps in s.parents]), 200

    @forward_or_dispatch()
    @jwt_required
    @securizer
    @validate_schema(step_parents)
    @lock_catalog
    def delete(self, step_id):
        s = Step.query.get_or_raise(step_id)
        parent_step_ids = request.get_json()['parent_step_ids']
        parent_steps = []
        for parent_step_id in parent_step_ids:
            parent_steps.append(Step.query.get_or_raise(parent_step_id))

        s.orchestration.delete_parents(s, parent_steps)

        db.session.commit()

        return dict(parent_step_ids=[str(ps.id) for ps in s.parents]), 200
