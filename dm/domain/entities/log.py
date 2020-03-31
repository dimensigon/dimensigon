import copy
import re
import typing as t

from dm.domain.entities.base import UUIDistributedEntityMixin
from dm.utils.typos import UUID
from dm.web import db

if t.TYPE_CHECKING:
    from dm.domain.entities import Server


class Log(db.Model, UUIDistributedEntityMixin):
    __tablename__ = 'D_log'

    src_server_id = db.Column(UUID, db.ForeignKey('D_server.id'), nullable=False)
    target = db.Column(db.Text, nullable=False)
    include = db.Column(db.Text)
    exclude = db.Column(db.Text)
    dst_server_id = db.Column(UUID, db.ForeignKey('D_server.id'), nullable=False)
    dest_folder = db.Column(db.Text)
    recursive = db.Column(db.Boolean, default=False)

    source_server = db.relationship("Server", foreign_keys=[src_server_id])
    destination_server = db.relationship("Server", foreign_keys=[dst_server_id])

    __table_args__ = (db.UniqueConstraint('src_server_id', 'target', 'dst_server_id'),)

    def __init__(self, source_server: 'Server', target: str, destination_server: 'Server', dest_folder=None,
                 include=None, exclude=None, recursive=False, **kwargs):
        UUIDistributedEntityMixin.__init__(self, **kwargs)

        self.source_server = source_server
        self.target = target
        self.destination_server = destination_server
        self.dest_folder = dest_folder
        self.include = include
        self._re_include = re.compile(self.include or '')
        self.exclude = exclude
        self._re_exclude = re.compile(self.exclude or '^$')
        self.recursive = recursive

    def __str__(self):
        return f"{self.source_server}:{self.target} -> {self.destination_server}:{self.dest_folder}"

    def to_json(self):
        data = super().to_json()
        data.update(src_server_id=str(self.source_server.id), target=self.target, include=self.include,
                    exclude=self.exclude, dst_server_id=str(self.destination_server.id), dest_folder=self.dest_folder,
                    recursive=self.recursive)
        return data

    def from_json(cls, kwargs):
        kwargs = copy.deepcopy(kwargs)
        kwargs['source_server'] = Server.query.get(kwargs.pop('src_server_id'))
        kwargs['destination_server'] = Server.query.get(kwargs.pop('dst_server_id'))
        return super().from_json(kwargs)
