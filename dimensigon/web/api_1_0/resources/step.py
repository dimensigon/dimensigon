import uuid

from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import Step, Orchestration, ActionTemplate, ActionType
from dimensigon.web import db, errors
from dimensigon.web.decorators import securizer, forward_or_dispatch, validate_schema, lock_catalog
from dimensigon.web.helpers import filter_query, check_param_in_uri
from dimensigon.web.json_schemas import step_post, step_put, step_patch


class StepList(Resource):

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self):
        query = filter_query(Step, request.args)
        return [s.to_json(split_lines=check_param_in_uri('split_lines')) for s in query.all()]

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @validate_schema(step_post)
    @lock_catalog
    def post(self):
        json_data = request.get_json()
        if not isinstance(json_data, list):
            json_data = [json_data]

        new_id_steps = []
        rid2step = {}
        dependencies = {}
        o: Orchestration = None
        for json_step in json_data:
            rid = json_step.pop('id', None)
            if rid is not None and rid in rid2step.keys():
                raise errors.DuplicatedId(rid)
            if o is None or str(o.id) != json_step.get('orchestration_id'):
                o = Orchestration.query.get_or_raise(json_step.pop('orchestration_id'))
            else:
                json_step.pop('orchestration_id')
            if 'action_template_id' in json_step:
                json_step['action_template'] = ActionTemplate.query.get_or_raise(json_step.pop('action_template_id'))
            elif 'action_type' in json_step:
                json_step['action_type'] = ActionType[json_step.pop('action_type')]
            dep = {'parent_step_ids': json_step.pop('parent_step_ids', []),
                                 'children_step_ids': json_step.pop('children_step_ids', [])}
            s = o.add_step(**json_step)
            db.session.add(s)
            new_id_steps.append(str(s.id))
            if rid:
                rid2step[rid] = s
            else:
                rid2step[new_id_steps[-1]] = s
                rid = new_id_steps[-1]
            dependencies[rid] = dep


        # process dependencies
        for rid, dep in dependencies.items():
            if rid not in rid2step:
                continue
            step = rid2step[rid]
            parents = []
            for p_s_id in dep['parent_step_ids']:
                if p_s_id in rid2step:
                    parents.append(rid2step[p_s_id])
                else:
                    parents.append(Step.query.get_or_raise(p_s_id))
            o.set_parents(step, parents)
            children = []
            for c_s_id in dep['children_step_ids']:
                if c_s_id in rid2step:
                    children.append(rid2step[c_s_id])
                else:
                    children.append(Step.query.get_or_raise(c_s_id))
            o.set_children(step, children)

        db.session.commit()

        return {'id': new_id_steps[0]} if len(new_id_steps) == 1 else {'ids': new_id_steps}, 201


class StepResource(Resource):
    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self, step_id):
        return Step.query.get_or_raise(step_id).to_json(split_lines=check_param_in_uri('split_lines'))

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @validate_schema(step_put)
    @lock_catalog
    def put(self, step_id):
        s: Step = Step.query.get_or_raise(step_id)
        json_data = request.get_json()
        s.undo = json_data.pop('undo')
        s.action_template = ActionTemplate.query.get_or_raise(json_data.pop('action_template_id'))
        # remove dependencies
        s.orchestration.set_parents(s, [])
        s.orchestration.set_children(s, [])

        parent_step_ids = json_data.pop('parent_step_ids', [])
        parent_steps = []
        for parent_step_id in parent_step_ids:
            cs = Step.query.get_or_raise(parent_step_id)
            parent_steps.append(cs)
            s.orchestration.set_parents(s, parent_steps)

        children_step_ids = json_data.pop('children_step_ids', [])
        children_steps = []
        for children_step_id in children_step_ids:
            cs = Step.query.get_or_raise(children_step_id)
            children_steps.append(cs)
            s.orchestration.set_children(s, children_steps)

        s.stop_on_error = json_data.pop('stop_on_error', None)
        s.stop_undo_on_error = json_data.pop('stop_undo_on_error', None)
        s.undo_on_error = json_data.pop('undo_on_error', None)
        aux = json_data.get('expected_stdout', None)
        s.expected_stdout = aux if isinstance(aux, str) or aux is None else '\n'.join(aux)



        aux = json_data.get('expected_stderr', None)
        s.expected_stderr = aux if isinstance(aux, str) or aux is None else '\n'.join(aux)

        s.expected_rc = json_data.pop('expected_rc', None)
        s.parameters = json_data.pop('parameters', None)
        s.system_kwargs = json_data.pop('system_kwargs', None)
        s.target = json_data.pop('target', None)
        s.name = json_data.pop('name', None)

        aux = json_data.get('pre_process', None)
        s.pre_process = aux if isinstance(aux, str) or aux is None else '\n'.join(aux)

        aux = json_data.get('post_process', None)
        s.post_process = aux if isinstance(aux, str) or aux is None else '\n'.join(aux)

        aux = json_data.get('description', None)
        s.description = aux if isinstance(aux, str) or aux is None else '\n'.join(aux)

        db.session.commit()

        return {}, 204

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @validate_schema(step_patch)
    @lock_catalog
    def patch(self, step_id):
        s: Step = Step.query.get_or_raise(step_id)
        json_data = request.get_json()
        if 'undo' in json_data:
            s.undo = json_data.pop('undo')
        if 'action_template_id' in json_data:
            s.action_template = ActionTemplate.query.get_or_raise(json_data.pop('action_template_id'))
        if 'parent_step_ids' in json_data:
            parent_step_ids = json_data.pop('parent_step_ids')
            parent_steps = []
            for parent_step_id in parent_step_ids:
                ps = Step.query.get_or_raise(parent_step_id)
                parent_steps.append(ps)
                s.orchestration.add_parents(s, parent_steps)
        if 'children_step_ids' in json_data:
            children_step_ids = json_data.pop('children_step_ids')
            children_steps = []
            for children_step_id in children_step_ids:
                cs = Step.query.get_or_raise(children_step_id)
                children_steps.append(cs)
                s.orchestration.add_children(s, children_steps)

        for k, v in json_data.items():
            setattr(s, k, v)

        if 'expected_stdout' in json_data and s.expected_stdout != json_data.get('expected_stdout'):
            aux = json_data.get('expected_stdout')
            s.expected_stdout = aux if isinstance(aux, str) or aux is None else '\n'.join(aux)

        if 'expected_stderr' in json_data and s.expected_stderr != json_data.get('expected_stderr'):
            aux = json_data.get('expected_stderr')
            s.expected_stderr = aux if isinstance(aux, str) or aux is None else '\n'.join(aux)

        if 'pre_process' in json_data and s.pre_process != json_data.get('pre_process'):
            aux = json_data.get('pre_process')
            s.pre_process = aux if isinstance(aux, str) or aux is None else '\n'.join(aux)

        if 'post_process' in json_data and s.post_process != json_data.get('post_process'):
            aux = json_data.get('post_process')
            s.post_process = aux if isinstance(aux, str) or aux is None else '\n'.join(aux)

        if 'description' in json_data and s.description != json_data.get('description'):
            aux = json_data.get('description')
            s.description = aux if isinstance(aux, str) or aux is None else '\n'.join(aux)

        db.session.commit()

        return {}, 204

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    @lock_catalog
    def delete(self, step_id):
        s: Step = Step.query.get_or_raise(step_id)
        s.orchestration.delete_step(s)

        db.session.delete(s)
        db.session.commit()

        return {}, 204
