import copy
import typing as t

from dm.domain.entities import Server
from dm.domain.entities.base import DistributedEntityMixin, UUIDistributedEntityMixin
from dm.utils.typos import UUID
from dm.web import db


class SoftwareServerAssociation(db.Model, DistributedEntityMixin):
    __tablename__ = "D_software_server"
    order = 20

    software_id = db.Column(UUID, db.ForeignKey("D_software.id"), primary_key=True, nullable=False)
    server_id = db.Column(UUID, db.ForeignKey("D_server.id"), primary_key=True, nullable=False)
    path = db.Column(db.Text, nullable=False)

    software = db.relationship("Software", back_populates="ssas", uselist=False)
    server = db.relationship("Server", backref="software_list", uselist=False)

    def to_json(self):
        data = super().to_json()
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


class Software(db.Model, UUIDistributedEntityMixin):
    __tablename__ = "D_software"
    order = 10

    name = db.Column(db.String(80), nullable=False)
    version = db.Column(db.String(40), nullable=False)
    family = db.Column(db.String(50))
    filename = db.Column(db.String(256))
    size = db.Column(db.Integer)
    checksum = db.Column(db.Text())

    ssas: t.List[SoftwareServerAssociation] = db.relationship("SoftwareServerAssociation", back_populates="software")

    __table_args__ = (
        db.UniqueConstraint('name', 'version', name='D_software_u01'),)

    def __init__(self, name, version, family=None, filename=None, size=None, checksum=None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.version = version
        self.family = family
        self.filename = filename
        self.size = size
        self.checksum = checksum

    def to_json(self):
        data = super().to_json()
        data.update({'name': self.name, 'version': self.version, 'family': self.family,
                     'filename': self.filename, 'size': self.size, 'checksum': self.checksum})
        return data

    @classmethod
    def from_json(cls, kwargs):
        kwargs = copy.deepcopy(kwargs)
        return super().from_json(kwargs)
