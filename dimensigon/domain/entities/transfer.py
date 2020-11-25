import os
import time
import typing as t
from enum import Enum

import dimensigon.defaults
from dimensigon.domain.entities import Software
from dimensigon.domain.entities.base import EntityReprMixin, UUIDEntityMixin
from dimensigon.utils import typos
from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import UtcDateTime
from dimensigon.web import db


class Status(Enum):
    WAITING_CHUNKS = 1
    IN_PROGRESS = 2
    COMPLETED = 3
    CHECKSUM_ERROR = 4
    SIZE_ERROR = 5
    CANCELLED = 6
    TRANSFER_ERROR = 7


class Transfer(UUIDEntityMixin, EntityReprMixin, db.Model):
    __tablename__ = "L_transfer"

    software_id = db.Column(db.ForeignKey('D_software.id'))
    dest_path = db.Column(db.Text, nullable=False)
    num_chunks = db.Column(db.Integer, nullable=False)
    status = db.Column(typos.Enum(Status), nullable=False, default=Status.WAITING_CHUNKS)
    created_on = db.Column(UtcDateTime(timezone=True))
    started_on = db.Column(UtcDateTime(timezone=True))
    ended_on = db.Column(UtcDateTime(timezone=True))
    _filename = db.Column("filename", db.String(256))
    _size = db.Column("size", db.Integer)
    _checksum = db.Column("checksum", db.Text())

    software = db.relationship("Software", uselist=False)

    def __init__(self, software: t.Union[Software, str], dest_path: str, num_chunks: int, status: Status = None,
                 size: int = None, checksum: str = None, created_on=None,
                 **kwargs):
        super().__init__(**kwargs)
        if isinstance(software, Software):
            self.software = software
        else:
            self._filename = software
            if size is None:
                ValueError("'size' must be specified when sending a file")
            self._size = size
            if checksum is None:
                ValueError("'checksum' must be specified when sending a file")
            self._checksum = checksum
        self.dest_path = dest_path
        self.num_chunks = num_chunks
        self.status = status or Status.WAITING_CHUNKS
        self.created_on = created_on or get_now()

    def to_json(self):
        json = dict(id=str(self.id), dest_path=self.dest_path,
                    num_chunks=self.num_chunks, status=self.status.name,
                    created_on=self.created_on.strftime(dimensigon.defaults.DATETIME_FORMAT),
                    file=os.path.join(self.dest_path, self.filename))

        if self.software:
            json.update(software_id=str(self.software.id))
        else:
            json.update(size=self._size, checksum=self._checksum)

        if self.started_on:
            json.update(started_on=self.started_on.strftime(dimensigon.defaults.DATETIME_FORMAT))
        if self.ended_on:
            json.update(ended_on=self.ended_on.strftime(dimensigon.defaults.DATETIME_FORMAT))
        return json

    @property
    def filename(self):
        if self.software:
            return self.software.filename
        else:
            return self._filename

    @property
    def size(self):
        if self.software:
            return self.software.size
        else:
            return self._size

    @property
    def checksum(self):
        if self.software:
            return self.software.checksum
        else:
            return self._checksum

    def wait_transfer(self, timeout=None, refresh_interval: float = 0.02) -> Status:
        timeout = timeout or 300
        refresh_interval = refresh_interval
        start = time.time()
        db.session.refresh(self)
        delta = 0
        while self.status in (Status.IN_PROGRESS, Status.WAITING_CHUNKS) and delta < timeout:
            time.sleep(refresh_interval)
            db.session.refresh(self)
            delta = time.time() - start

        return self.status
