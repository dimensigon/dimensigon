import uuid
from datetime import datetime
import typing as t

from dm.domain.entities.base import DistributedEntityMixin, EntityWithId
from dm.utils.typos import UUID, Kwargs, JSON
from dm.web import db


class ServiceOrchestration(db.Model, DistributedEntityMixin):
    __tablename__ = 'D_service_orchestration'
    id = db.Column(UUID, primary_key=True)
    service_id = db.Column(UUID, db.ForeignKey('D_service.id'))
    orchestration_id = db.Column(UUID, db.ForeignKey('D_orchestration.id'))
    execution_time = db.Column(db.DateTime, default=datetime.now())


class Service(EntityWithId, DistributedEntityMixin):
    __tablename__ = 'D_service'

    name = db.Column(db.String(255), nullable=False)
    details = db.Column(JSON)
    created_on = db.Column(db.DateTime, nullable=False, default=datetime.now)
    last_ping = db.Column(db.DateTime)
    status = db.Column(db.String(40))

    executions = db.relationship("Execution", back_populates="service")
    orchestrations = db.relationship("Orchestration", secondary="D_service_orchestration", order_by="ServiceOrchestration.execution_time")

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


    def __str__(self):
        return self.__repr__()
