import typing as t
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

    software = db.relationship("Software", back_populates="ssas", uselist=False)
    server = db.relationship("Server", back_populates="software_list", uselist=False)

    def to_json(self):
        return {'software_id': str(self.software.id), 'server_id': str(self.server.id), 'path': self.file}


class Software(db.Model, EntityReprMixin, DistributedEntityMixin):
    __tablename__ = "D_software"

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(80), nullable=False)
    version = db.Column(db.String(40), nullable=False)
    family = db.Column(db.Enum(Family), nullable=False)
    filename = db.Column(db.String(256))
    size = db.Column(db.Integer)
    checksum = db.Column(db.Text())

    ssas: t.List[SoftwareServerAssociation] = db.relationship("SoftwareServerAssociation", back_populates="software")

    __table_args__ = (
        db.UniqueConstraint('name', 'version', name='D_software_u01'),)


    def to_json(self):
        return {'id': str(self.id), 'name': self.name, 'version': self.version, 'family': self.family.name.lower(),
                'filename': self.filename, 'size': self.size, 'checksum': self.checksum,
                'servers': [str(ssa.server.id) for ssa in self.ssas]}
