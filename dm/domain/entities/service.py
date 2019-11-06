import typing as t
import uuid
from datetime import datetime

from dm.domain.entities.orchestration import Orchestration
from dm.domain.entities import Server
from dm.utils.datamark import data_mark
from dm.framework.domain import Entity, Id


class Service(Entity):
    __id__ = Id(factory=uuid.uuid1)

    @data_mark
    def __init__(self, name: str, servers: t.List[Server], details: str, orchestrations: t.List[Orchestration],
                 status: str, created: datetime, last_ping: datetime = None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.servers = servers
        self.details = details
        self.orchestrations = orchestrations
        self.status = status
        self.created = created
        self.last_ping = last_ping
