import json
import typing as t
import uuid
from datetime import datetime

from dimensigon import defaults
from dimensigon.domain.entities.base import EntityReprMixin
from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.web import db
from .server import Server
from ...utils.helpers import is_iterable_not_string, get_now

if t.TYPE_CHECKING:
    from dimensigon.use_cases.operations import CompletedProcess


# class Status(enum.Enum):
#     PENDING = enum.auto()
#     EXECUTING = enum.auto()
#     FINISHED = enum.auto()
#     ROLLING_BACK = enum.auto()
#     ROLLED_BACK = enum.auto()
#     CANCELLED = enum.auto()
#     ERROR = enum.auto()


class StepExecution(db.Model, EntityReprMixin):
    __tablename__ = 'L_execution'

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)

    start_time = db.Column(UtcDateTime(timezone=True), nullable=False, default=get_now())
    end_time = db.Column(UtcDateTime(timezone=True))
    params = db.Column(db.JSON)
    rc = db.Column(db.Integer)
    stdout = db.Column(db.Text)
    stderr = db.Column(db.Text)
    success = db.Column(db.Boolean)
    step_id = db.Column(UUID, db.ForeignKey('D_step.id'), nullable=False)
    server_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    orch_execution_id = db.Column(UUID)

    step = db.relationship("Step")
    server = db.relationship("Server", foreign_keys=[server_id])
    orch_execution = db.relationship("OrchExecution", foreign_keys=[orch_execution_id],
                                     primaryjoin="OrchExecution.id==StepExecution.orch_execution_id",
                                     uselist=False, backref="step_executions")

    def load_completed_result(self, cp: 'CompletedProcess'):
        self.success = cp.success
        self.stdout = cp.stdout
        self.stderr = cp.stderr
        if cp.pre_post_error:
            self.stderr += '\nError on pre/post process: '
            if str(cp.pre_post_error):
                self.stderr += str(cp.pre_post_error)
            else:
                self.stderr += str(cp.pre_post_error.__class__.__name__)
        self.rc = cp.rc
        self.start_time = cp.start_time
        self.end_time = cp.end_time

    def to_json(self, human=False):
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
                stdout = self.stdout
            try:
                stderr = json.loads(self.stderr)
            except:
                stderr = self.stderr
        else:
            data.update(
                server_id=str(getattr(self.server, 'id', None)) if getattr(self.server, 'id', None) else None)
            stdout = self.stdout
            stderr = self.stderr
        data.update(stdout=stdout)
        data.update(stderr=stderr)
        return data


class OrchExecution(db.Model, EntityReprMixin):
    __tablename__ = 'L_orch_execution'

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
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
    parent_orch_execution_id = db.Column(UUID, db.ForeignKey('L_orch_execution.id'))
    server_id = db.Column(UUID, db.ForeignKey('D_server.id'))

    orchestration = db.relationship("Orchestration")
    _executor = db.relationship("User")
    service = db.relationship("Service")
    parent_orch_execution = db.relationship("OrchExecution", uselist=False)
    server = db.relationship("Server", foreign_keys=[server_id])

    @property
    def executor(self):
        return self._executor if self._executor else self.parent_orch_execution

    def to_json(self, add_step_exec=False, human=False):
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
            for k, v in self.target.items():
                if is_iterable_not_string(v):
                    d[k] = [str(Server.query.get(s) or s) for s in v]
                else:
                    d[k] = str(Server.query.get(v) or v)
            data.update(target=d)
            data.update(executor=str(self._executor) if self._executor else None)
            data.update(service=str(self.service) if self.service else None)
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
                data.update(server=None)
        else:
            data.update(target=self.target)
            data.update(
                orchestration_id=str(getattr(self.orchestration, 'id', None)) if getattr(self.orchestration, 'id',
                                                                                         None) else None)
            data.update(
                executor_id=str(getattr(self._executor, 'id', None)) if getattr(self._executor, 'id', None) else None)
            data.update(
                service_id=str(getattr(self.service, 'id', None)) if getattr(self.service, 'id', None) else None)
            data.update(
                server_id=str(getattr(self.server, 'id', None)) if getattr(self.server,
                                                                           'id', None) else None)
        data.update(params=self.params)
        data.update(success=self.success)
        data.update(undo_success=self.undo_success)
        data.update(message=self.message)
        if self.parent_orch_execution:
            data.update(parent_orch_execution_id=str(self.parent_orch_execution.id))
        if add_step_exec:
            data.update(steps=[e.to_json(human) for e in self.step_executions])
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

