import time
from datetime import datetime
from enum import Enum, auto

from flask import current_app

import dm.defaults
from dm.domain.entities import Software
from dm.domain.entities.base import EntityReprMixin, UUIDEntityMixin
from dm.web import db


class Status(Enum):
    WAITING_CHUNKS = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    CHECKSUM_ERROR = auto()
    SIZE_ERROR = auto()
    CANCELED = auto()


class Transfer(db.Model, UUIDEntityMixin, EntityReprMixin):
    __tablename__ = "L_transfer"

    software_id = db.Column(db.ForeignKey('D_software.id'), nullable=False)
    dest_path = db.Column(db.Text, nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    num_chunks = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(Status), nullable=False, default=Status.WAITING_CHUNKS)
    created_on = db.Column(db.DateTime(), default=datetime.now())
    started_on = db.Column(db.DateTime())
    ended_on = db.Column(db.DateTime())

    software = db.relationship("Software", uselist=False)

    def __init__(self, software: Software, dest_path: str, filename: str, num_chunks: int, status: Status = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.software = software
        self.dest_path = dest_path
        self.filename = filename
        self.num_chunks = num_chunks
        self.status = status or Status.WAITING_CHUNKS

    def to_json(self):
        try:
            format = current_app.config['DATETIME_FORMAT']
        except:
            format = dm.defaults.DATETIME_FORMAT

        json = dict(id=str(self.id), software_id=str(self.software.id), dest_path=self.dest_path,
                    filename=self.filename, num_chunks=self.num_chunks, status=self.status.name,
                    created_on=self.created_on.strftime(format))
        if self.started_on:
            json.update(started_on=self.started_on)
        if self.ended_on:
            json.update(ended_on=self.ended_on)

        return json

    def wait_transfer(self, timeout=None, refresh_interval: float = None) -> Status:
        timeout = timeout or 300
        refresh_interval = refresh_interval or 1
        start = time.time()
        db.session.refresh(self)
        delta = 0
        while self.status in (Status.IN_PROGRESS, Status.WAITING_CHUNKS) and delta < timeout:
            time.sleep(refresh_interval)
            db.session.refresh(self)
            delta = time.time() - start

        return self.status
