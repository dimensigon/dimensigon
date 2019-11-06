import asyncio
import uuid
from contextlib import suppress
from threading import Event

from dm.domain.entities import Server
from dm.framework.domain import Entity, Id
from dm.utils.pygtail import Pygtail


class Log(Entity, Pygtail):
    __id__ = Id(factory=uuid.uuid1)

    def __init__(self, file: str, server: Server, dest_folder, dest_name=None, time=60, **kwargs):
        Entity.__init__(self, id=kwargs.pop('id', None))
        Pygtail.__init__(self, file=file, offset_mode='manual', **kwargs)
        self.server = server
        self.dest_folder = dest_folder
        self.dest_name = dest_name
        self.time = time

    def __repr__(self):
        data = [f"{k}={v}" for k, v in self.__dict__]

        return "Log(" + ', '.join(data) + ")"

    def __str__(self):
        return f"{self.file} -> {self.server}://{self.dest_folder}"

    def __del__(self):
        Pygtail.__del__(self)
