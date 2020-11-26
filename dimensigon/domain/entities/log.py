import copy
import re
import typing as t
from enum import Enum

from dimensigon.domain.entities.base import UUIDistributedEntityMixin, SoftDeleteMixin
from dimensigon.utils import typos
from dimensigon.web import db

if t.TYPE_CHECKING:
    from dimensigon.domain.entities import Server


class Mode(Enum):
    REPO_MIRROR = 0
    REPO_ROOT = 1
    MIRROR = 2
    FOLDER = 3


class Log(UUIDistributedEntityMixin, SoftDeleteMixin, db.Model):
    __tablename__ = 'D_log'

    src_server_id = db.Column(typos.UUID, db.ForeignKey('D_server.id'), nullable=False)
    target = db.Column(db.Text, nullable=False)
    include = db.Column(db.Text)
    exclude = db.Column(db.Text)
    dst_server_id = db.Column(typos.UUID, db.ForeignKey('D_server.id'), nullable=False)
    mode = db.Column(typos.Enum(Mode))
    dest_folder = db.Column(db.Text)
    recursive = db.Column(db.Boolean, default=False)
    _old_target = db.Column("$$target", db.Text)

    source_server = db.relationship("Server", foreign_keys=[src_server_id], back_populates="log_sources")
    destination_server = db.relationship("Server", foreign_keys=[dst_server_id], back_populates="log_destinations")

    __table_args__ = (db.UniqueConstraint('src_server_id', 'target', 'dst_server_id'),)

    def __init__(self, source_server: 'Server', target: str, destination_server: 'Server', dest_folder=None,
                 include=None, exclude=None, recursive=False, mode=Mode.REPO_MIRROR, **kwargs):
        super().__init__(**kwargs)

        self.source_server = source_server
        self.target = target
        self.destination_server = destination_server
        self.dest_folder = dest_folder
        if self.dest_folder is None:
            self.mode = mode
        else:
            self.mode = Mode.FOLDER
        self.include = include
        self._re_include = re.compile(self.include or '')
        self.exclude = exclude
        self._re_exclude = re.compile(self.exclude or '^$')
        self.recursive = recursive

    def __str__(self):
        return f"{self.source_server}:{self.target} -> {self.destination_server}:{self.dest_folder}"

    def to_json(self, human=False, include: t.List[str] = None, exclude: t.List[str] = None, **kwargs):
        data = super().to_json(**kwargs)
        if self.source_server.id is None or self.destination_server.id is None:
            raise RuntimeError('Set ids for servers before')
        data.update(target=self.target, include=self.include,
                    exclude=self.exclude, dest_folder=self.dest_folder,
                    recursive=self.recursive, mode=self.mode.name)
        if human:
            data.update(src_server=str(self.source_server.name), dst_server=str(self.destination_server.name))
        else:
            data.update(src_server_id=str(self.source_server.id), dst_server_id=str(self.destination_server.id))

        if include:
            data = {k: v for k, v in data.items() if k in include}
        if exclude:
            data = {k: v for k, v in data.items() if k not in exclude}
        return data

    @classmethod
    def from_json(cls, kwargs) -> 'Log':
        from dimensigon.domain.entities import Server
        kwargs = copy.deepcopy(kwargs)
        kwargs['mode'] = Mode[kwargs.get('mode')]
        kwargs['source_server'] = Server.query.get(kwargs.pop('src_server_id'))
        kwargs['destination_server'] = Server.query.get(kwargs.pop('dst_server_id'))
        return super().from_json(kwargs)
