from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource

from dimensigon.domain.entities import StepExecution, OrchExecution
from dimensigon.web.decorators import securizer, forward_or_dispatch
from dimensigon.web.helpers import filter_query, check_param_in_uri


class StepExecutionList(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(StepExecution, request.args)
        return [e.to_json(human=check_param_in_uri('human'), split_lines=True) for e in
                query.order_by(StepExecution.start_time).all()]


class StepExecutionResource(Resource):
    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self, execution_id):
        return StepExecution.query.get_or_raise(execution_id).to_json(human=check_param_in_uri('human'),
                                                                      split_lines=True)


class OrchestrationExecutionRelationship(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self, orchestration_id):
        query = filter_query(OrchExecution, request.args)
        return [oe.to_json(human=check_param_in_uri('human')) for oe in
                query.filter_by(orchestration_id=orchestration_id).order_by(OrchExecution.start_time).all()]


class OrchExecStepExecRelationship(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self, execution_id):
        query = filter_query(StepExecution, request.args)
        return [oe.to_json(human=check_param_in_uri('human')) for oe in
                query.filter_by(orch_execution_id=execution_id).order_by(StepExecution.start_time).all()]


class OrchExecutionList(Resource):

    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self):
        query = filter_query(OrchExecution, request.args)
        return [
            oe.to_json(human=check_param_in_uri('human'), add_step_exec=check_param_in_uri('steps'), split_lines=True)
            for oe in
            query.order_by(OrchExecution.start_time).all()]


class OrchExecutionResource(Resource):
    @forward_or_dispatch()
    @jwt_required
    @securizer
    def get(self, execution_id):
        return OrchExecution.query.get_or_raise(execution_id).to_json(add_step_exec=check_param_in_uri('steps'),
                                                                      human=check_param_in_uri('human'),
                                                                      split_lines=True)
