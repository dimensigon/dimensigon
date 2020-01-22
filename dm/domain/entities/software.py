import uuid
from enum import Enum, auto

from dm.domain.entities.base import DistributedEntityMixin, EntityReprMixin
from dm.utils.typos import UUID
from dm.web import db


class Family(Enum):
    MIDDLEWARE = auto()


class SoftwareServerAssociation(db.Model, DistributedEntityMixin):
    __tablename__ = "D_software_server"
    software_id = db.Column(UUID, db.ForeignKey("D_software.id"), primary_key=True)
    server_id = db.Column(UUID, db.ForeignKey("D_server.id"), primary_key=True)
    path = db.Column(db.Text, nullable=False)

    software = db.relationship("Software", back_populates="servers", uselist=False)
    server = db.relationship("Server", back_populates="software_list", uselist=False)


class Software(db.Model, EntityReprMixin, DistributedEntityMixin):
    __tablename__ = "D_software"

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(80), nullable=False)
    version = db.Column(db.String(40))
    family = db.Enum(Family, nullable=False)
    size_bytes = db.Column(db.Integer)
    checksum = db.Column(db.Text())

    servers = db.relationship("SoftwareServerAssociation", back_populates="software")
