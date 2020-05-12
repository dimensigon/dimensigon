import typing as t
import uuid
from datetime import datetime

from dm import defaults
from dm.domain.entities.base import EntityReprMixin
from dm.utils.typos import UUID, JSONEncodedDict, JSON
from dm.web import db
from .server import Server

if t.TYPE_CHECKING:
    from dm.use_cases.operations import CompletedProcess


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

    start_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    end_time = db.Column(db.DateTime)
    params = db.Column(JSONEncodedDict)
    rc = db.Column(db.Integer)
    stdout = db.Column(db.Text)
    stderr = db.Column(db.Text)
    success = db.Column(db.Boolean)
    fetched_data = db.Column(JSON)
    step_id = db.Column(UUID, db.ForeignKey('D_step.id'), nullable=False)
    execution_server_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    source_server_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    orch_execution_id = db.Column(UUID)

    step = db.relationship("Step")

    execution_server = db.relationship("Server", foreign_keys=[execution_server_id])
    source_server = db.relationship("Server", foreign_keys=[source_server_id])

    orch_execution = db.relationship("OrchExecution", foreign_keys=[orch_execution_id],
                                     primaryjoin="OrchExecution.id==StepExecution.orch_execution_id",
                                     uselist=False, backref="executions")

    def load_completed_result(self, cp: 'CompletedProcess'):
        self.success = cp.success
        self.stdout = cp.stdout
        self.stderr = cp.stderr
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
        if human:
            data.update(execution_server=str(self.execution_server) if self.execution_server else None)
            data.update(source_server=str(self.source_server) if self.source_server else None)
            data.update(step=str(self.action_template))
        else:
            data.update(step_id=str(getattr(self.step, 'id', None)) if getattr(self.step, 'id', None) else None)
            data.update(
                execution_server_id=str(getattr(self.execution_server, 'id', None)) if getattr(self.execution_server,
                                                                                               'id', None) else None)
            data.update(
                source_server_id=str(getattr(self.source_server, 'id', None)) if getattr(self.source_server, 'id',
                                                                                         None) else None)
        data.update(rc=self.rc, stdout=self.stdout, stderr=self.stderr, success=self.success,
                    fetched_data=self.fetched_data)
        return data


class OrchExecution(db.Model, EntityReprMixin):
    __tablename__ = 'L_orch_execution'

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    end_time = db.Column(db.DateTime)
    orchestration_id = db.Column(UUID, db.ForeignKey('D_orchestration.id'), nullable=False)
    target = db.Column(JSON)
    params = db.Column(JSON)
    executor_id = db.Column(UUID, db.ForeignKey('D_user.id'))
    service_id = db.Column(UUID, db.ForeignKey('D_service.id'))
    success = db.Column(db.Boolean)
    undo_success = db.Column(db.Boolean)
    message = db.Column(db.Text)

    orchestration = db.relationship("Orchestration")
    executor = db.relationship("User")
    service = db.relationship("Service")

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
                d[k] = [str(Server.query.get(s)) for s in v]
            data.update(target=d)
            data.update(executor=str(self.executor) if self.executor else None)
            data.update(service=str(self.service) if self.service else None)
            data.update(
                orchestration=str(self.orchestration) if self.orchestration else None)
        else:
            d = {}
            for k, v in self.target.items():
                d[k] = [str(s) for s in v]
            data.update(target=d)
            data.update(
                orchestration_id=str(getattr(self.orchestration, 'id', None)) if getattr(self.orchestration, 'id',
                                                                                         None) else None)
            data.update(
                executor_id=str(getattr(self.executor, 'id', None)) if getattr(self.executor, 'id', None) else None)
            data.update(service_id=str(getattr(self.service, 'id', None)) if getattr(self.service, 'id', None) else None)
        data.update(params=self.params)
        data.update(success=self.success)
        data.update(undo_success=self.undo_success)
        data.update(message=self.message)
        if add_step_exec:
            data.update(steps=[e.to_json(human) for e in self.executions])
        return data

    @classmethod
    def from_json(cls, kwargs):
        if 'id' in kwargs:
            kwargs['id'] = uuid.UUID(kwargs.get('id'))
        if 'start_time' in kwargs:
            kwargs['start_time'] = datetime.strptime(kwargs.get('start_time'), defaults.DATETIME_FORMAT)
        if 'end_time' in kwargs:
            kwargs['end_time'] = datetime.strptime(kwargs.get('end_time'), defaults.DATETIME_FORMAT)
        # if 'executor_id' in kwargs:
        #     from dm.domain.entities import User
        #     kwargs['executor'] = User.query.get(kwargs.pop('executor_id'))
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

