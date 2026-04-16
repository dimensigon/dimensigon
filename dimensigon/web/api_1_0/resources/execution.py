from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import StepExecution, OrchExecution
from dimensigon.web import db
from dimensigon.web.decorators import securizer, forward_or_dispatch
from dimensigon.web.helpers import filter_query, check_param_in_uri, get_or_raise


class StepExecutionList(Resource):

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self):
        stmt = filter_query(StepExecution, request.args).order_by(StepExecution.start_time)
        return [e.to_json(human=check_param_in_uri('human'), split_lines=True) for e in
                db.session.execute(stmt).scalars().all()]


class StepExecutionResource(Resource):
    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self, execution_id):
        return get_or_raise(StepExecution, execution_id).to_json(human=check_param_in_uri('human'),
                                                                  split_lines=True)


class OrchestrationExecutionRelationship(Resource):

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self, orchestration_id):
        stmt = filter_query(OrchExecution, request.args).where(
            OrchExecution.orchestration_id == orchestration_id
        ).order_by(OrchExecution.start_time)
        return [oe.to_json(human=check_param_in_uri('human')) for oe in
                db.session.execute(stmt).scalars().all()]


class OrchExecStepExecRelationship(Resource):

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self, execution_id):
        stmt = filter_query(StepExecution, request.args).where(
            StepExecution.orch_execution_id == execution_id
        ).order_by(StepExecution.start_time)
        return [oe.to_json(human=check_param_in_uri('human')) for oe in
                db.session.execute(stmt).scalars().all()]


class OrchExecutionList(Resource):

    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self):
        stmt = filter_query(OrchExecution, request.args).order_by(OrchExecution.start_time)
        return [
            oe.to_json(human=check_param_in_uri('human'), add_step_exec=check_param_in_uri('steps'), split_lines=True)
            for oe in
            db.session.execute(stmt).scalars().all()]


class OrchExecutionResource(Resource):
    @forward_or_dispatch()
    @jwt_required()
    @securizer
    def get(self, execution_id):
        return get_or_raise(OrchExecution, execution_id).to_json(add_step_exec=check_param_in_uri('steps'),
                                                               human=check_param_in_uri('human'),
                                                               split_lines=True)
