import uuid
from datetime import datetime

from dm.domain.entities.base import DistributedEntityMixin, EntityReprMixin
from dm.utils.helpers import get_now
from dm.utils.typos import UUID, Kwargs, UtcDateTime
from dm.web import db


class ServiceOrchestration(db.Model, EntityReprMixin, DistributedEntityMixin):
    __tablename__ = 'D_service_orchestration'
    order = 50
    id = db.Column(UUID, primary_key=True)
    service_id = db.Column(UUID, db.ForeignKey('D_service.id'))
    orchestration_id = db.Column(UUID, db.ForeignKey('D_orchestration.id'))
    execution_time = db.Column(UtcDateTime(), default=get_now())


class Service(db.Model, EntityReprMixin, DistributedEntityMixin):
    __tablename__ = 'D_service'
    order = 40

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    details = db.Column(db.JSON)
    created_on = db.Column(UtcDateTime(timezone=True), nullable=False, default=get_now)
    last_ping = db.Column(UtcDateTime(timezone=True))
    status = db.Column(db.String(40))

    orchestrations = db.relationship("Orchestration", secondary="D_service_orchestration", order_by="ServiceOrchestration.execution_time")

    def __init__(self, name: str, details: Kwargs, status: str, created_on: datetime = get_now(),
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
