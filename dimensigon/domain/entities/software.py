import copy
import os
import typing as t

from packaging.version import parse

from dimensigon.domain.entities import Server
from dimensigon.domain.entities.base import DistributedEntityMixin, UUIDistributedEntityMixin, SoftDeleteMixin
from dimensigon.utils.typos import UUID
from dimensigon.web import db


class SoftwareServerAssociation(DistributedEntityMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "D_software_server_association"
    order = 30

    software_id = db.Column(UUID, db.ForeignKey("D_software.id"), primary_key=True, nullable=False)
    server_id = db.Column(UUID, db.ForeignKey("D_server.id"), primary_key=True, nullable=False)
    path = db.Column(db.Text, nullable=False)

    software = db.relationship("Software", back_populates="ssas", uselist=False)
    server = db.relationship("Server", backref="software_list", uselist=False)

    def to_json(self, **kwargs):
        data = super().to_json(**kwargs)
        data.update({'software_id': str(self.software.id), 'server_id': str(self.server.id), 'path': self.path})
        return data

    @classmethod
    def from_json(cls, kwargs):
        kwargs = copy.deepcopy(kwargs)
        kwargs['software'] = Software.query.get(kwargs.get('software_id'))
        kwargs['server'] = Server.query.get(kwargs.get('server_id'))
        super().from_json(kwargs)
        try:
            o = cls.query.get((kwargs['software_id'], kwargs['server_id']))
        except RuntimeError as e:
            o = None
        if o:
            for k, v in kwargs.items():
                if getattr(o, k) != v:
                    setattr(o, k, v)
            return o
        else:
            return cls(**kwargs)

    @property
    def file(self):
        return os.path.join(self.path or '', self.software.filename or '')


class Software(UUIDistributedEntityMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "D_software"
    order = 20

    name = db.Column(db.String(80), nullable=False)
    version = db.Column(db.String(40), nullable=False)

    family = db.Column(db.String(50))
    filename = db.Column(db.String(256))
    size = db.Column(db.Integer)
    checksum = db.Column(db.Text())
    _old_name = db.Column("$$name", db.String(255))

    ssas: t.List[SoftwareServerAssociation] = db.relationship("SoftwareServerAssociation", back_populates="software")

    __table_args__ = (
        db.UniqueConstraint('name', 'version', name='D_software_u01'),)

    def __init__(self, name, version, filename, family=None, size=None, checksum=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.version = version
        self.family = family
        self.filename = filename
        self.size = size
        self.checksum = checksum

    def to_json(self, servers=False):
        data = super().to_json()
        data.update({'name': self.name, 'version': self.version, 'family': self.family,
                     'filename': self.filename, 'size': self.size, 'checksum': self.checksum})
        if servers:
            servers = []
            for ssa in self.ssas:
                server_data = dict(server=ssa.server.name, server_id=str(ssa.server.id), path=ssa.path)
                servers.append(server_data)
            data.update(servers=servers)
        return data

    @property
    def parsed_version(self):
        return parse(self.version) if self.version else None

    @classmethod
    def from_json(cls, kwargs):
        kwargs = copy.deepcopy(kwargs)
        return super().from_json(kwargs)

    def __str__(self):
        return f"{self.name}.{self.version}"

    def delete(self):
        super().delete()
        for ssa in self.ssas:
            ssa.delete()
