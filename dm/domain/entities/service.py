import uuid
from datetime import datetime

from sqlalchemy import event, func
from sqlalchemy.orm import object_session

from dm.domain.entities import Execution, Orchestration
from dm.domain.entities.base import DistributedEntityMixin
from dm.domain.entities.orchestration import Step
from dm.utils.typos import UUID, Kwargs, JSON, ScalarListType
from dm.web import db


class Service(db.Model, DistributedEntityMixin):
    __tablename__ = 'D_service'

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    details = db.Column(JSON)
    created_on = db.Column(db.DateTime, nullable=False, default=datetime.now)
    last_ping = db.Column(db.DateTime)
    status = db.Column(db.String(40))
    _orchestrations = db.Column("orchestrations", ScalarListType(UUID))

    executions = db.relationship("Execution", back_populates="service")

    def __init__(self, name: str, details: Kwargs, status: str, created_on: datetime = datetime.now(),
                 last_ping: datetime = None, id=uuid.uuid4(), **kwargs):
        DistributedEntityMixin.__init__(self, **kwargs)
        self.id = id
        self.name = name
        self.details = details
        self.status = status
        self.created_on = created_on
        self.last_ping = last_ping

    def to_json(self):
        return {'id': self.id, 'name': self.name, 'details': self.details,
                'last_ping': self.last_ping.strftime("%d/%m/%Y %H:%M:%S"),
                'status': self.status}

    @property
    def orchestrations(self):
        return [Orchestration.get() for o_id in self._orchestrations]

    @orchestrations.setter
    def orchestrations(self, orchestrations):
        self._orchestrations = [o.id for o in orchestrations]

    def __repr__(self):
        return '<Service %s>' % self.id

    def __str__(self):
        return self.__repr__()
