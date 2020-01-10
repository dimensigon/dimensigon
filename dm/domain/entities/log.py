import asyncio
import uuid
import typing as t

from sqlalchemy import orm


from dm.utils.pygtail import Pygtail
from dm.utils.typos import UUID
from dm.web import db

if t.TYPE_CHECKING:
    from dm.domain.entities import Server


class Log(db.Model):
    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    file = db.Column(db.Text, nullable=False)
    server_id = db.Column(UUID, db.ForeignKey('D_server.id'), nullable=False)
    dest_folder = db.Column(db.Text)
    offset_file = db.Column(db.Text)

    server = db.relationship("Server")

    def __init__(self, file: str, server: 'Server', id: uuid.UUID = None, dest_folder=None, offset_file=None):
        self.id = id
        self.file = file
        self.server = server
        self.dest_folder = dest_folder
        self.offset_file = offset_file
        self.pytail = Pygtail(file=self.file, offset_mode='manual', offset_file=self.offset_file)

    @orm.reconstructor
    def init_on_load(self):
        self.pytail = Pygtail(file=self.file, offset_mode='manual', offset_file=self.offset_file)

    def __str__(self):
        return f"{self.file} -> {self.server}://{self.dest_folder}"

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.id}>'
