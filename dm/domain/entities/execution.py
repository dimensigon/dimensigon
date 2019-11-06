import typing as t
import uuid
from datetime import datetime

from dm.framework.domain import Entity, Id

if t.TYPE_CHECKING:
    from dm.domain.entities.server import Server
    from dm.domain.entities.orchestration import Orchestration, Step


class Execution(Entity):
    __id__ = Id(factory=uuid.uuid1)

    def __init__(self, orchestration: 'Orchestration', step: 'Step', server: 'Server', params: dict, stdout: str = None,
                 stderr: str = None, rc: int = None, start_time: datetime = None, end_time: datetime = None, **kwargs):
        super().__init__(**kwargs)
        self.orchestration = orchestration
        self.step = step
        self.server = server
        self.params = params
        self.stdout = stdout
        self.stderr = stderr
        self.rc = rc
        self.start_time = start_time
        self.end_time = end_time
