import enum
import typing as t
import uuid
from datetime import datetime

from dm.domain.entities.base import EntityWithId
from dm.utils.typos import UUID
from dm.web import db

if t.TYPE_CHECKING:
    pass


class Status(enum.Enum):
    PENDING = enum.auto()
    EXECUTING = enum.auto()
    FINISHED = enum.auto()
    ROLLING_BACK = enum.auto()
    ROLLED_BACK = enum.auto()
    CANCELLED = enum.auto()
    ERROR = enum.auto()


class Execution(EntityWithId):
    __tablename__ = 'L_execution'

    step_id = db.Column(db.Integer(), db.ForeignKey('D_step.id'), nullable=False)
    status = db.Column(db.Enum(Status))
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    end_time = db.Column(db.DateTime, nullable=True)
    rc = db.Column(db.Integer, nullable=True)
    stdout = db.Column(db.Text, nullable=True)
    stderr = db.Column(db.Text, nullable=True)
    executor = db.Column(UUID, nullable=True)
    server_id = db.Column(UUID, db.ForeignKey('D_server.id'), nullable=False)
    service_id = db.Column(UUID, db.ForeignKey('D_service.id'), nullable=False)

    step = db.relationship("Step")
    service = db.relationship("Service", back_populates="executions")
    server = db.relationship("Server")
