import uuid
from datetime import datetime
from enum import Enum, auto

from flask import current_app

from dm.defaults import DEFAULT_DATETIME_FORMAT
from dm.domain.entities.base import EntityReprMixin
from dm.utils.typos import UUID
from dm.web import db


class Status(Enum):
    WAITING_CHUNKS = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    CHECKSUM_ERROR = auto()
    SIZE_ERROR = auto()
    CANCELED = auto()


class Transfer(db.Model, EntityReprMixin):
    __tablename__ = "L_transfer"

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    software_id = db.Column(db.ForeignKey('D_software.id'), nullable=False)
    dest_path = db.Column(db.Text, nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    num_chunks = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(Status), nullable=False, default=Status.WAITING_CHUNKS)
    created_on = db.Column(db.DateTime(), default=datetime.now())
    started_on = db.Column(db.DateTime())
    ended_on = db.Column(db.DateTime())

    software = db.relationship("Software", uselist=False)

    def to_json(self):
        try:
            format = current_app.config['DATETIME_FORMAT']
        except:
            format = DEFAULT_DATETIME_FORMAT

        json = dict(id=str(self.id), software_id=str(self.software.id), dest_path=self.dest_path,
                    filename=self.filename, num_chunks=self.num_chunks, status=self.status.name,
                    created_on=self.created_on.strftime(format))
        if self.started_on:
            json.update(started_on=self.started_on)
        if self.ended_on:
            json.update(ended_on=self.ended_on)

        return json