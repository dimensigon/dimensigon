import uuid
from enum import Enum, auto

from dm.framework.domain import Entity, Id
from dm.utils.datamark import data_mark


class ActionType(Enum):
    ANSIBLE = auto()
    PYTHON = auto()
    NATIVE = auto()
    ORCHESTRATION = auto()
    TEST = auto()


class ActionTemplate(Entity):
    __id__ = Id(factory=uuid.uuid1)

    @data_mark
    def __init__(self, name: str, version: int, action_type: ActionType, code: str, parameters: dict = None,
                 system_kwargs: dict = None, expected_output: str = None, expected_rc: int = None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.version = version
        self.action_type = action_type
        self.code = code
        self.parameters = parameters or {}
        self.system_kwargs = system_kwargs or {}
        self.expected_output = expected_output
        self.expected_rc = expected_rc
