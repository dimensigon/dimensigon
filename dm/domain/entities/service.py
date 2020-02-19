import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import relationship

from dm.domain.entities.base import DistributedEntityMixin, EntityReprMixin
from dm.model import Base
from dm.utils.typos import UUID, Kwargs, JSON


class ServiceOrchestration(Base, EntityReprMixin, DistributedEntityMixin):
    __tablename__ = 'D_service_orchestration'
    id = sa.Column(UUID, primary_key=True)
    service_id = sa.Column(UUID, sa.ForeignKey('D_service.id'))
    orchestration_id = sa.Column(UUID, sa.ForeignKey('D_orchestration.id'))
    execution_time = sa.Column(sa.DateTime, default=datetime.now())


class Service(Base, EntityReprMixin, DistributedEntityMixin):
    __tablename__ = 'D_service'

    id = sa.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = sa.Column(sa.String(255), nullable=False)
    details = sa.Column(JSON)
    created_on = sa.Column(sa.DateTime, nullable=False, default=datetime.now)
    last_ping = sa.Column(sa.DateTime)
    status = sa.Column(sa.String(40))

    executions = relationship("Execution", back_populates="service")
    orchestrations = relationship("Orchestration", secondary="D_service_orchestration",
                                  order_by="ServiceOrchestration.execution_time")

    def __init__(self, name: str, details: Kwargs, status: str, created_on: datetime = datetime.now(),
                 last_ping: datetime = None, id: uuid.UUID = None, **kwargs):
        DistributedEntityMixin.__init__(self, **kwargs)
        self.id = id
        self.name = name
        self.details = details
        self.status = status
        self.created_on = created_on
        self.last_ping = last_ping

    def to_json(self):
        return {'id': str(self.id), 'name': self.name, 'details': self.details,
                'last_ping': self.last_ping.strftime("%d/%m/%Y %H:%M:%S"),
                'status': self.status}
