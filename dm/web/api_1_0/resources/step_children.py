from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.domain.entities import Step
from dm.web import db
from dm.web.decorators import forward_or_dispatch, securizer, validate_schema, lock_catalog
from dm.web.json_schemas import step_children


class StepRelationshipChildrenResource(Resource):
    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self, step_id):
        s: Step = Step.query.get_or_404(step_id)
        return dict(child_step_ids=[str(cs.id) for cs in s.children]), 200

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(step_children)
    @lock_catalog
    def patch(self, step_id):
        s: Step = Step.query.get_or_404(step_id)
        child_step_ids = request.get_json()['child_step_ids']
        child_steps = []
        for child_step_id in child_step_ids:
            child_steps.append(Step.query.get_or_404(child_step_id))
        s.orchestration.set_children(s, child_steps)

        db.session.commit()

        return dict(child_step_ids=[str(cs.id) for cs in s.children]), 200

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(step_children)
    @lock_catalog
    def post(self, step_id):
        s = Step.query.get_or_404(step_id)
        child_step_ids = request.get_json()['child_step_ids']
        child_steps = []
        for child_step_id in child_step_ids:
            child_steps.append(Step.query.get_or_404(child_step_id))
        s.orchestration.add_children(s, child_steps)

        db.session.commit()

        return dict(child_step_ids=[str(cs.id) for cs in s.children]), 200

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(step_children)
    @lock_catalog
    def delete(self, step_id):
        s = Step.query.get_or_404(step_id)
        child_step_ids = request.get_json()['child_step_ids']
        child_steps = []
        for child_step_id in child_step_ids:
            child_steps.append(Step.query.get_or_404(child_step_id))

        s.orchestration.delete_children(s, child_steps)

        db.session.commit()

        return dict(child_step_ids=[str(cs.id) for cs in s.children]), 200