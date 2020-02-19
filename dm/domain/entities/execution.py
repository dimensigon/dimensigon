import enum
import typing as t
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import relationship

from dm.domain.entities.base import EntityReprMixin
from dm.model import Base
from dm.utils.typos import UUID

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


class Execution(Base, EntityReprMixin):
    __tablename__ = 'L_execution'

    id = sa.Column(UUID, primary_key=True, default=uuid.uuid4)
    step_id = sa.Column(sa.Integer(), sa.ForeignKey('D_step.id'), nullable=False)
    status = sa.Column(sa.Enum(Status))
    start_time = sa.Column(sa.DateTime, nullable=False, default=datetime.now)
    end_time = sa.Column(sa.DateTime, nullable=True)
    rc = sa.Column(sa.Integer, nullable=True)
    stdout = sa.Column(sa.Text, nullable=True)
    stderr = sa.Column(sa.Text, nullable=True)
    executor = sa.Column(UUID, nullable=True)
    server_id = sa.Column(UUID, sa.ForeignKey('D_server.id'), nullable=False)
    service_id = sa.Column(UUID, sa.ForeignKey('D_service.id'), nullable=False)

    step = relationship("Step")
    service = relationship("Service", back_populates="executions")
    server = relationship("Server")
