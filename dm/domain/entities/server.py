import typing as t
import uuid
from datetime import datetime

from dm.utils.datamark import data_mark
from dm.framework.domain import Entity, Id


class Server(Entity):
    __id__ = Id(factory=uuid.uuid1)

    @data_mark
    def __init__(self, name: str, ip: str, port: int, birth: datetime = None, keep_alive: int = None,
                 available: bool = None, granules: t.List[str] = None, route: t.List['Server'] = None,
                 alt_route: t.List['Server'] = None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.ip = ip
        self.port = port
        self.birth = birth or datetime.now()
        self.keep_alive = keep_alive
        self.available = available
        self.granules = granules
        self.route = route
        self.alt_route = alt_route

    def __str__(self):
        return self.name + ':' + str(self.port)
