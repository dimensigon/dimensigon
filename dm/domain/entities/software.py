import typing as t
import uuid
from enum import Enum, auto

import sqlalchemy as sa
from sqlalchemy.orm import relationship

from dm.domain.entities.base import DistributedEntityMixin, EntityReprMixin
from dm.model import Base
from dm.utils.typos import UUID


class Family(Enum):
    MIDDLEWARE = auto()


class SoftwareServerAssociation(Base, DistributedEntityMixin):
    __tablename__ = "D_software_server"
    software_id = sa.Column(UUID, sa.ForeignKey("D_software.id"), primary_key=True)
    server_id = sa.Column(UUID, sa.ForeignKey("D_server.id"), primary_key=True)
    path = sa.Column(sa.Text, nullable=False)

    software = relationship("Software", back_populates="ssas", uselist=False)
    server = relationship("Server", back_populates="software_list", uselist=False)

    def to_json(self):
        return {'software_id': str(self.software.id), 'server_id': str(self.server.id), 'path': self.file}


class Software(Base, EntityReprMixin, DistributedEntityMixin):
    __tablename__ = "D_software"

    id = sa.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = sa.Column(sa.String(80), nullable=False)
    version = sa.Column(sa.String(40), nullable=False)
    family = sa.Column(sa.Enum(Family), nullable=False)
    filename = sa.Column(sa.String(256))
    size = sa.Column(sa.Integer)
    checksum = sa.Column(sa.Text())

    ssas: t.List[SoftwareServerAssociation] = relationship("SoftwareServerAssociation", back_populates="software")

    __table_args__ = (
        sa.UniqueConstraint('name', 'version', name='D_software_u01'),)

    def to_json(self):
        return {'id': str(self.id), 'name': self.name, 'version': self.version, 'family': self.family.name.lower(),
                'filename': self.filename, 'size': self.size, 'checksum': self.checksum,
                'servers': [str(ssa.server.id) for ssa in self.ssas]}
