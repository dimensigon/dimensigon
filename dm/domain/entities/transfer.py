import time
import uuid
from datetime import datetime
from enum import Enum, auto

import sqlalchemy as sa
from flask import current_app
from sqlalchemy.orm import relationship

import dm.defaults
from dm.db import session
from dm.domain.entities import Software
from dm.domain.entities.base import EntityReprMixin
from dm.model import Base
from dm.utils.typos import UUID


class Status(Enum):
    WAITING_CHUNKS = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    CHECKSUM_ERROR = auto()
    SIZE_ERROR = auto()
    CANCELED = auto()


class Transfer(Base, EntityReprMixin):
    __tablename__ = "L_transfer"

    id = sa.Column(UUID, primary_key=True, default=uuid.uuid4)
    software_id = sa.Column(sa.ForeignKey('D_software.id'), nullable=False)
    dest_path = sa.Column(sa.Text, nullable=False)
    filename = sa.Column(sa.String(256), nullable=False)
    num_chunks = sa.Column(sa.Integer, nullable=False)
    status = sa.Column(sa.Enum(Status), nullable=False, default=Status.WAITING_CHUNKS)
    created_on = sa.Column(sa.DateTime(), default=datetime.now())
    started_on = sa.Column(sa.DateTime())
    ended_on = sa.Column(sa.DateTime())

    software = relationship("Software", uselist=False)

    def __init__(self, software: Software, dest_path: str, filename: str, num_chunks: int, status: Status = None,
                 id: uuid.UUID = None):
        self.software = software
        self.dest_path = dest_path
        self.filename = filename
        self.num_chunks = num_chunks
        self.status = status or Status.WAITING_CHUNKS
        self.id = id

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
        session.refresh(self)
        delta = 0
        while self.status in (Status.IN_PROGRESS, Status.WAITING_CHUNKS) and delta < timeout:
            time.sleep(refresh_interval)
            session.refresh(self)
            delta = time.time() - start

        return self.status
