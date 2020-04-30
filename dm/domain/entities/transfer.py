import time
import typing as t
from datetime import datetime
from enum import Enum, auto

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

    software_id = db.Column(db.ForeignKey('D_software.id'))
    dest_path = db.Column(db.Text, nullable=False)
    num_chunks = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(Status), nullable=False, default=Status.WAITING_CHUNKS)
    created_on = db.Column(db.DateTime())
    started_on = db.Column(db.DateTime())
    ended_on = db.Column(db.DateTime())
    _filename = db.Column("filename", db.String(256))
    _size = db.Column("size", db.Integer)
    _checksum = db.Column("checksum", db.Text())

    software = db.relationship("Software", uselist=False)

    def __init__(self, software: t.Union[Software, str], dest_path: str, num_chunks: int, status: Status = None,
                 size: int = None, checksum: str = None, created_on=None,
                 **kwargs):
        UUIDEntityMixin.__init__(self, **kwargs)
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
        self.created_on = created_on or datetime.now()

    def to_json(self):
        json = dict(id=str(self.id), dest_path=self.dest_path,
                    num_chunks=self.num_chunks, status=self.status.name,
                    created_on=self.created_on.strftime(dm.defaults.DATETIME_FORMAT))
        if self.software:
            json.update(software_id=str(self.software.id))
        else:
            json.update(filename=self._filename, size=self._size, checksum=self._checksum)
        if self.started_on:
            json.update(started_on=self.started_on)
        if self.ended_on:
            json.update(ended_on=self.ended_on)

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
