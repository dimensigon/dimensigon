import typing as t
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import relationship, reconstructor

from dm.domain.entities.base import EntityReprMixin
from dm.model import Base
from dm.utils.pygtail import Pygtail
from dm.utils.typos import UUID

if t.TYPE_CHECKING:
    from dm.domain.entities import Server


class Log(Base, EntityReprMixin):
    __tablename__ = 'L_log'
    id = sa.Column(UUID, primary_key=True, default=uuid.uuid4)
    file = sa.Column(sa.Text, nullable=False)
    server_id = sa.Column(UUID, sa.ForeignKey('D_server.id'), nullable=False)
    dest_folder = sa.Column(sa.Text)
    offset_file = sa.Column(sa.Text)

    server = relationship("Server")

    def __init__(self, file: str, server: 'Server', id: uuid.UUID = None, dest_folder=None, offset_file=None):
        self.id = id
        self.file = file
        self.server = server
        self.dest_folder = dest_folder
        self.offset_file = offset_file
        self.pytail = Pygtail(file=self.file, offset_mode='manual', offset_file=self.offset_file)

    @reconstructor
    def init_on_load(self):
        self.pytail = Pygtail(file=self.file, offset_mode='manual', offset_file=self.offset_file)

    def __str__(self):
        return f"{self.file} -> {self.server}://{self.dest_folder}"
