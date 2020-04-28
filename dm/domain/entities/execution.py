import enum
import typing as t
import uuid
from datetime import datetime

from dm import defaults
from dm.domain.entities.base import EntityReprMixin
from dm.utils.typos import UUID
from dm.web import db

if t.TYPE_CHECKING:
    from dm.use_cases.operations import CompletedProcess


class Status(enum.Enum):
    PENDING = enum.auto()
    EXECUTING = enum.auto()
    FINISHED = enum.auto()
    ROLLING_BACK = enum.auto()
    ROLLED_BACK = enum.auto()
    CANCELLED = enum.auto()
    ERROR = enum.auto()


class Execution(db.Model, EntityReprMixin):
    __tablename__ = 'L_execution'

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)

    start_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    end_time = db.Column(db.DateTime)
    rc = db.Column(db.Integer)
    stdout = db.Column(db.Text)
    stderr = db.Column(db.Text)
    success = db.Column(db.Boolean)
    executor_id = db.Column(UUID, db.ForeignKey('D_user.id'))
    step_id = db.Column(UUID, db.ForeignKey('D_step.id'), nullable=True)
    execution_server_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    source_server_id = db.Column(UUID, db.ForeignKey('D_server.id'))
    service_id = db.Column(UUID, db.ForeignKey('D_service.id'))

    executor = db.relationship("User")
    step = db.relationship("Step")
    service = db.relationship("Service", back_populates="executions")
    execution_server = db.relationship("Server", foreign_keys=[execution_server_id])
    source_server = db.relationship("Server", foreign_keys=[source_server_id])

    def load_completed_result(self, cp: 'CompletedProcess'):
        self.success = cp.success
        self.stdout = cp.stdout
        self.stderr = cp.stderr
        self.rc = cp.rc
        self.start_time = cp.start_time
        self.end_time = cp.end_time

    def to_json(self):
        data = {}
        if self.id:
            data.update(id=str(self.id))
        if self.start_time:
            data.update(start_time=self.start_time.strftime(defaults.DATETIME_FORMAT))
        if self.end_time:
            data.update(end_time=self.end_time.strftime(defaults.DATETIME_FORMAT))
        data.update(executor_id=str(getattr(self.executor, 'id', None)) if getattr(self.executor, 'id', None) else None)
        data.update(step_id=str(getattr(self.step, 'id', None)) if getattr(self.step, 'id', None) else None)
        data.update(
            execution_server_id=str(getattr(self.execution_server, 'id', None)) if getattr(self.execution_server, 'id',
                                                                                           None) else None)
        data.update(source_server_id=str(getattr(self.source_server, 'id', None)) if getattr(self.source_server, 'id',
                                                                                             None) else None)
        data.update(service_id=str(getattr(self.service, 'id', None)) if getattr(self.service, 'id', None) else None)
        data.update(rc=self.rc, stdout=self.stdout, stderr=self.stderr, success=self.success, )
        return data


