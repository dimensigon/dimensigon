import copy
import os
import sys
import typing as t

from dimensigon.domain.entities import Server
from dimensigon.domain.entities.base import UUIDistributedEntityMixin, SoftDeleteMixin, DistributedEntityMixin
from dimensigon.utils import typos
from dimensigon.utils.typos import Id
from dimensigon.web import db
from dimensigon.web.helpers import QueryWithSoftDelete

if t.TYPE_CHECKING:
    ...

if sys.version_info < (3, 8):
    Destination_Server = t.Dict[str, t.Union[Id, Server, str]]
else:
    class Destination_Server(t.TypedDict):
        dst_server_id: Id
        dest_folder: str

Destination_Servers = t.List[t.Union[t.Tuple[Server, str], t.Tuple[Id, str], Server, Destination_Server]]


class FileServerAssociation(DistributedEntityMixin, SoftDeleteMixin, db.Model):
    __tablename__ = 'D_file_server_association'
    order = 30

    file_id = db.Column(typos.UUID, db.ForeignKey('D_file.id'), nullable=False, primary_key=True)
    dst_server_id = db.Column(typos.UUID, db.ForeignKey('D_server.id'), nullable=False, primary_key=True)
    dest_folder = db.Column(db.Text)
    l_mtime = db.Column(db.INTEGER)

    file = db.relationship("File")
    destination_server = db.relationship("Server")

    @property
    def destination_folder(self):
        return self.dest_folder or self.file.dest_folder or os.path.dirname(self.file.target)

    @property
    def target(self):
        return os.path.join(self.destination_folder, os.path.basename(self.file.target))

    def to_json(self, human=False, **kwargs) -> t.Dict:
        data = super().to_json(**kwargs)
        if human:
            data.update({'file': {'target': self.file.target, 'src_server': self.file.source_server.name,
                                  'dst_server': str(self.destination_server.name),
                                  'dest_folder': self.dest_folder}})
        else:
            data.update({'file_id': str(self.file.id), 'dst_server_id': str(self.destination_server.id),
                         'dest_folder': self.dest_folder})
        return data

    @classmethod
    def from_json(cls, kwargs) -> 'FileServerAssociation':
        kwargs = copy.deepcopy(kwargs)
        kwargs['file'] = File.query.get_or_raise(kwargs.get('file_id'))
        kwargs['destination_server'] = Server.query.get_or_raise(kwargs.get('dst_server_id'))
        super().from_json(kwargs)
        try:
            o = cls.query.get((kwargs['file_id'], kwargs['dst_server_id']))
        except RuntimeError as e:
            o = None
        if o:
            for k, v in kwargs.items():
                if getattr(o, k) != v:
                    setattr(o, k, v)
            return o
        else:
            return cls(**kwargs)


class File(UUIDistributedEntityMixin, SoftDeleteMixin, db.Model):
    __tablename__ = 'D_file'
    order = 20

    src_server_id = db.Column(typos.UUID, db.ForeignKey('D_server.id'), nullable=False)
    target = db.Column(db.Text, nullable=False)
    dest_folder = db.Column(db.Text)
    _old_target = db.Column("$$target", db.Text)
    l_mtime = db.Column(db.INTEGER)

    source_server = db.relationship("Server")
    destinations: t.List[FileServerAssociation] = db.relationship("FileServerAssociation", lazy='joined')

    __table_args__ = (db.UniqueConstraint('src_server_id', 'target'),)

    query_class = QueryWithSoftDelete

    def __init__(self, source_server: Server, target: str,
                 dest_folder=None, destination_servers: Destination_Servers = None, **kwargs):
        super().__init__(**kwargs)

        self.source_server = source_server
        self.target = target
        self.dest_folder = dest_folder
        dest = []
        for ds in destination_servers or []:
            if isinstance(ds, Server):
                dest.append(FileServerAssociation(file=self, destination_server=ds))
            elif isinstance(ds, dict):

                dest.append(
                    FileServerAssociation(file=self, destination_server=Server.query.get(ds.get('dst_server_id')),
                                          dest_folder=ds.get('dest_folder')))
            elif isinstance(ds, tuple):
                if isinstance(ds[0], Server):
                    dest.append(FileServerAssociation(file=self, destination_server=ds[0], dest_folder=ds[1]))
                else:
                    dest.append(
                        FileServerAssociation(file=self, destination_server=Server.query.get(ds[0]), dest_folder=ds[1]))
        self.destinations = dest

    def __str__(self):
        return f"{self.source_server}:{self.target}"

    def to_json(self, human=False, destinations=False, include: t.List[str] = None,
                exclude: t.List[str] = None, **kwargs):
        data = super().to_json(**kwargs)
        if self.source_server.id is None:
            raise RuntimeError('Set ids for servers before')
        data.update(target=self.target, dest_folder=self.dest_folder)
        if human:
            data.update(src_server=str(self.source_server.name))
            if destinations:
                dest = []
                for d in self.destinations:
                    dest.append(dict(dst_server=d.destination_server.name, dest_folder=d.dest_folder))
                data.update(destinations=dest)
        else:
            data.update(src_server_id=str(self.source_server.id))
            if destinations:
                dest = []
                for d in self.destinations:
                    dest.append(dict(dst_server_id=d.destination_server.id, dest_folder=d.dest_folder))
                data.update(destinations=dest)

        if include:
            data = {k: v for k, v in data.items() if k in include}
        if exclude:
            data = {k: v for k, v in data.items() if k not in exclude}
        return data

    @classmethod
    def from_json(cls, kwargs) -> 'File':
        kwargs = copy.deepcopy(kwargs)
        kwargs['source_server'] = Server.query.get_or_raise(kwargs.pop('src_server_id'))
        return super().from_json(kwargs)

    def delete(self):
        for d in self.destinations:
            d.delete()
        return super().delete()
