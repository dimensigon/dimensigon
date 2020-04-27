from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dm.domain.entities import Step, Orchestration, ActionTemplate
from dm.domain.exceptions import CycleError
from dm.web import db
from dm.web.decorators import securizer, forward_or_dispatch, validate_schema, lock_catalog
from dm.web.helpers import filter_query
from dm.web.json_schemas import step_post, step_put, step_patch


class StepResourceList(Resource):

    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(Step, request.args)
        return [s.to_json() for s in query.all()]

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(step_post)
    @lock_catalog
    def post(self):
        json_data = request.get_json()
        if not isinstance(json_data, list):
            json_data = [json_data]

        new_id_steps = []
        id2step = {}
        o = None
        for json_step in json_data:
            if o is None:
                o = Orchestration.query.get_or_404(json_step.get('orchestration_id'))
            at = ActionTemplate.query.get_or_404(json_step.pop('action_template_id'))
            json_step['action_template'] = at
            parent_steps = []
            for parent_step_id in json_step.pop('parent_step_ids', []):
                if parent_step_id in id2step:
                    ps = id2step[parent_step_id]
                else:
                    ps = Step.query.get_or_404(parent_step_id)
                parent_steps.append(ps)
            json_step['parents'] = parent_steps
            child_steps = []
            for child_step_id in json_step.pop('child_step_ids', []):
                if child_step_id in id2step:
                    cs = id2step[child_step_id]
                else:
                    cs = Step.query.get_or_404(child_step_id)
                child_steps.append(cs)
            json_step['children'] = child_steps
            rid = json_step.pop('id', None)
            s = o.add_step(**json_step)
            new_id_steps.append(str(s.id))
            if rid:
                id2step[rid] = s

        db.session.commit()

        return {'step_id': new_id_steps[0]} if len(new_id_steps) == 1 else {'step_ids': new_id_steps}, 201


class StepResource(Resource):
    @forward_or_dispatch
    @jwt_required
    @securizer
    def get(self, step_id):
        return Step.query.get_or_404(step_id).to_json()

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(step_put)
    @lock_catalog
    def put(self, step_id):
        s: Step = Step.query.get_or_404(step_id)
        json_data = request.get_json()
        s.undo = json_data.pop('undo')
        s.action_template = ActionTemplate.query.get_or_404(json_data.pop('action_template_id'))
        # remove dependencies
        s.orchestration.set_parents(s, [])
        s.orchestration.set_children(s, [])

        parent_step_ids = json_data.pop('parent_step_ids', [])
        parent_steps = []
        for parent_step_id in parent_step_ids:
            cs = Step.query.get_or_404(parent_step_id)
            parent_steps.append(cs)
        try:
            s.orchestration.add_parents(s, parent_steps)
        except (CycleError, ValueError) as e:
            return {'error': str(e)}, 409

        child_step_ids = json_data.pop('child_step_ids', [])
        child_steps = []
        for child_step_id in child_step_ids:
            cs = Step.query.get_or_404(child_step_id)
            child_steps.append(cs)
        try:
            s.orchestration.add_children(s, child_steps)
        except (CycleError, ValueError) as e:
            return {'error': str(e)}, 409

        s.stop_on_error = json_data.pop('stop_on_error', None)
        s.stop_undo_on_error = json_data.pop('stop_undo_on_error', None)
        s.undo_on_error = json_data.pop('undo_on_error', None)
        s.expected_stdout = json_data.pop('expected_stdout', None)
        s.expected_stderr = json_data.pop('expected_stderr', None)
        s.expected_rc = json_data.pop('expected_rc', None)
        s.parameters = json_data.pop('parameters', None)
        s.system_kwargs = json_data.pop('system_kwargs', None)
        s.target = json_data.pop('target', None)

        db.session.commit()

        return {}, 204

    @forward_or_dispatch
    @jwt_required
    @securizer
    @validate_schema(step_patch)
    @lock_catalog
    def patch(self, step_id):
        s: Step = Step.query.get_or_404(step_id)
        json_data = request.get_json()
        if 'undo' in json_data:
            s.undo = json_data.pop('undo')
        if 'action_template_id' in json_data:
            s.action_template = ActionTemplate.query.get_or_404(json_data.pop('action_template_id'))
        if 'parent_step_ids' in json_data:
            parent_step_ids = json_data.pop('parent_step_ids')
            parent_steps = []
            for parent_step_id in parent_step_ids:
                ps = Step.query.get_or_404(parent_step_id)
                parent_steps.append(ps)
            try:
                s.orchestration.add_parents(s, parent_steps)
            except (CycleError, ValueError) as e:
                return {'error': str(e)}, 409
        if 'child_step_ids' in json_data:
            child_step_ids = json_data.pop('child_step_ids')
            child_steps = []
            for child_step_id in child_step_ids:
                cs = Step.query.get_or_404(child_step_id)
                child_steps.append(cs)
            try:
                s.orchestration.add_children(s, child_steps)
            except (CycleError, ValueError) as e:
                return {'error': str(e)}, 409

        for k, v in json_data.items():
            setattr(s, k, v)

        db.session.commit()

        return {}, 204

    @forward_or_dispatch
    @jwt_required
    @securizer
    @lock_catalog
    def delete(self, step_id):
        s: Step = Step.query.get_or_404(step_id)
        s.orchestration.delete_step(s)

        db.session.delete(s)
        db.session.commit()

        return {}, 204
