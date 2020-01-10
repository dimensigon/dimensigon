import uuid
from datetime import datetime

from sqlalchemy import event
from sqlalchemy.orm import object_session

from dm.domain.entities.base import DistributedEntityMixin
from dm.utils.typos import UUID, Kwargs
from dm.web import db


class Service(db.Model, DistributedEntityMixin):
    __tablename__ = 'D_service'

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text)
    created_on = db.Column(db.DateTime, nullable=False, default=datetime.now)
    last_ping = db.Column(db.DateTime)
    status = db.Column(db.String(40))

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

    def __repr__(self):
        return '<Service %s>' % self.id

    def __str__(self):
        return self.__repr__()
