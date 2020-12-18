import json
import typing as t
from datetime import datetime

from flask import current_app
from flask_jwt_extended import get_jwt_identity

from dimensigon import defaults
from dimensigon.domain.entities.base import EntityReprMixin, UUIDEntityMixin
from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.web import db
from .server import Server
from ...utils.helpers import is_iterable_not_string, get_now

if t.TYPE_CHECKING:
    from dimensigon.use_cases.operations import CompletedProcess


class StepExecution(UUIDEntityMixin, EntityReprMixin, db.Model):
    __tablename__ = 'L_step_execution'

    start_time = db.Column(UtcDateTime(timezone=True), nullable=False)
    end_time = db.Column(UtcDateTime(timezone=True))
    params = db.Column(db.JSON)
    rc = db.Column(db.Integer)
    stdout = db.Column(db.Text)
    stderr = db.Column(db.Text)
    success = db.Column(db.Boolean)
    step_id = db.Column(UUID, db.ForeignKey('D_step.id'), nullable=False)
    server_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    orch_execution_id = db.Column(UUID, db.ForeignKey('L_orch_execution.id'))
    pre_process_elapsed_time = db.Column(db.Float)
    execution_elapsed_time = db.Column(db.Float)
    post_process_elapsed_time = db.Column(db.Float)
    child_orch_execution_id = db.Column(UUID)

    step = db.relationship("Step")
    server = db.relationship("Server", foreign_keys=[server_id])
    orch_execution = db.relationship("OrchExecution", foreign_keys=[orch_execution_id],
                                     uselist=False, back_populates="step_executions")
    child_orch_execution = db.relationship("OrchExecution", uselist=False, foreign_keys=[child_orch_execution_id],
                                           primaryjoin="StepExecution.child_orch_execution_id==OrchExecution.id")

    # def __init__(self, *args, **kwargs):
    #     UUIDEntityMixin.__init__(self, **kwargs)

    def load_completed_result(self, cp: 'CompletedProcess'):
        self.success = cp.success
        self.stdout = cp.stdout
        self.stderr = cp.stderr
        self.rc = cp.rc

    def to_json(self, human=False, split_lines=False):
        data = {}
        if self.id:
            data.update(id=str(self.id))
        if self.start_time:
            data.update(start_time=self.start_time.strftime(defaults.DATETIME_FORMAT))
        if self.end_time:
            data.update(end_time=self.end_time.strftime(defaults.DATETIME_FORMAT))
        data.update(params=self.params)
        data.update(step_id=str(getattr(self.step, 'id', None)) if getattr(self.step, 'id', None) else None)
        data.update(rc=self.rc, success=self.success)
        if human:
            data.update(server=str(self.server) if self.server else None)
            try:
                stdout = json.loads(self.stdout)
            except:
                stdout = self.stdout.split('\n') if split_lines and self.stdout and '\n' in self.stdout else self.stdout
            try:
                stderr = json.loads(self.stderr)
            except:
                stderr = self.stderr.split('\n') if split_lines and self.stderr and '\n' in self.stderr else self.stderr
        else:
            data.update(
                server_id=str(getattr(self.server, 'id', None)) if getattr(self.server, 'id', None) else None)
            stdout = self.stdout.split('\n') if split_lines and self.stdout and '\n' in self.stdout else self.stdout
            stderr = self.stderr.split('\n') if split_lines and self.stderr and '\n' in self.stderr else self.stderr
        data.update(stdout=stdout)
        data.update(stderr=stderr)
        if self.child_orch_execution_id:
            data.update(child_orch_execution_id=str(self.child_orch_execution_id))
        data.update(
            pre_process_elapsed_time=self.pre_process_elapsed_time) if self.pre_process_elapsed_time is not None else None
        data.update(
            execution_elapsed_time=self.execution_elapsed_time) if self.execution_elapsed_time is not None else None
        data.update(
            post_process_elapsed_time=self.post_process_elapsed_time) if self.post_process_elapsed_time is not None else None
        return data


class OrchExecution(UUIDEntityMixin, EntityReprMixin, db.Model):
    __tablename__ = 'L_orch_execution'

    start_time = db.Column(UtcDateTime(timezone=True), nullable=False, default=get_now)
    end_time = db.Column(UtcDateTime(timezone=True))
    orchestration_id = db.Column(UUID, db.ForeignKey('D_orchestration.id'), nullable=False)
    target = db.Column(db.JSON)
    params = db.Column(db.JSON)
    executor_id = db.Column(UUID, db.ForeignKey('D_user.id'))
    service_id = db.Column(UUID, db.ForeignKey('D_service.id'))
    success = db.Column(db.Boolean)
    undo_success = db.Column(db.Boolean)
    message = db.Column(db.Text)
    server_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    parent_step_execution_id = db.Column(UUID)

    orchestration = db.relationship("Orchestration")
    executor = db.relationship("User")
    service = db.relationship("Service")
    step_executions = db.relationship("StepExecution", back_populates="orch_execution",
                                      order_by="StepExecution.start_time")

    server = db.relationship("Server", foreign_keys=[server_id])
    parent_step_execution = db.relationship("StepExecution", uselist=False, foreign_keys=[parent_step_execution_id],
                                            primaryjoin="OrchExecution.parent_step_execution_id==StepExecution.id")

    # def __init__(self, *args, **kwargs):
    #     UUIDEntityMixin.__init__(self, **kwargs)

    def to_json(self, add_step_exec=False, human=False, split_lines=False):
        data = {}
        if self.id:
            data.update(id=str(self.id))
        if self.start_time:
            data.update(start_time=self.start_time.strftime(defaults.DATETIME_FORMAT))
        if self.end_time:
            data.update(end_time=self.end_time.strftime(defaults.DATETIME_FORMAT))
        if human:
            # convert target ids to server names
            d = {}
            if isinstance(self.target, dict):
                for k, v in self.target.items():
                    if is_iterable_not_string(v):
                        d[k] = [str(Server.query.get(s) or s) for s in v]
                    else:
                        d[k] = str(Server.query.get(v) or v)
            elif isinstance(self.target, list):
                d = [str(Server.query.get(s) or s) for s in self.target]
            else:
                d = str(Server.query.get(self.target) or self.target)
            data.update(target=d)
            if self.executor:
                data.update(executor=str(self.executor))
            if self.service:
                data.update(service=str(self.service))
            if self.orchestration:
                data.update(
                    orchestration=dict(id=str(self.orchestration.id), name=self.orchestration.name,
                                       version=self.orchestration.version))
            else:
                data.update(
                    orchestration=None)
            if self.server:
                data.update(server=dict(id=str(self.server.id), name=self.server.name))
        else:
            data.update(target=self.target)
            if self.orchestration_id or getattr(self.orchestration, 'id', None):
                data.update(orchestration_id=str(self.orchestration_id or getattr(self.orchestration, 'id', None)))
            if self.executor_id or getattr(self.executor, 'id', None):
                data.update(executor_id=str(self.executor_id or getattr(self.executor, 'id', None)))
            if self.service_id or getattr(self.service, 'id', None):
                data.update(service_id=str(self.server_id or getattr(self.service, 'id', None)))
            if self.server_id or getattr(self.server, 'id', None):
                data.update(server_id=str(self.server_id or getattr(self.server, 'id', None)))
        data.update(params=self.params)
        data.update(success=self.success)
        data.update(undo_success=self.undo_success)
        data.update(message=self.message)

        if self.parent_step_execution_id and not add_step_exec:
            data.update(parent_step_execution_id=str(self.parent_step_execution_id))
        if add_step_exec:
            steps = []
            for se in self.step_executions:
                se: StepExecution

                se_json = se.to_json(human, split_lines=split_lines)
                if se.child_orch_execution:
                    se_json['orch_execution'] = se.child_orch_execution.to_json(add_step_exec=add_step_exec,
                                                                                split_lines=split_lines,
                                                                                human=human)
                elif se.child_orch_execution_id:
                    from dimensigon.web.network import get, Response
                    from dimensigon.network.auth import HTTPBearerAuth
                    from flask_jwt_extended import create_access_token
                    params = ['steps']
                    if human:
                        params.append('human')

                    try:
                        resp = get(se.server, 'api_1_0.orchexecutionresource',
                                   view_data=dict(execution_id=se.child_orch_execution_id, params=params))
                    except Exception as e:
                        current_app.logger.exception(f"Exception while trying to acquire orch execution "
                                                     f"{se.child_orch_execution_id} from {se.server}")
                        resp = Response(exception=e)

                    if resp.ok:
                        se_json['orch_execution'] = resp.msg
                        se_json.pop('child_orch_execution_id', None)

                steps.append(se_json)
            # steps.sort(key=lambda x: x.start_time)
            data.update(steps=steps)
        return data

    @classmethod
    def from_json(cls, kwargs):
        if 'start_time' in kwargs:
            kwargs['start_time'] = datetime.strptime(kwargs.get('start_time'), defaults.DATETIME_FORMAT)
        if 'end_time' in kwargs:
            kwargs['end_time'] = datetime.strptime(kwargs.get('end_time'), defaults.DATETIME_FORMAT)
        try:
            o = cls.query.get(kwargs.get('id'))
        except RuntimeError as e:
            o = None
        if o:
            for k, v in kwargs.items():
                if getattr(o, k) != v:
                    setattr(o, k, v)
            return o
        else:
            return cls(**kwargs)
