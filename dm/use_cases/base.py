import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import dm.use_cases.deployment as dpl
from dm.domain.entities import Server, ActionType, Step
from dm.network import TypeMsg

if t.TYPE_CHECKING:
    from dm.use_cases import Mediator


@dataclass
class Token:
    """
    Class that saves relation between a sent message and its asynchronous return.
    """
    id: int
    source: str
    destination: str

    @property
    def uid(self):
        return self.source + '.' + self.destination + '.' + str(id)


class Scope(Enum):
    UPGRADE = 10
    ORCHESTRATION = 30
    CATALOG = 40

    def __lt__(self, other):
        return self.value < other.value


@dataclass
class Message:
    source: Server
    destination: Server
    msg_type: TypeMsg
    content: t.Any
    token: Token
    created_on: datetime = datetime.now()
    session: int = field(default=None)


@dataclass
class MsgExecution:
    source: Server
    destination: Server
    function_name: str
    args: t.Sequence
    kwargs: t.Dict[str, t.Any]
    created_on: datetime = datetime.now()


# class IGateway(ABC):
#
#     def __init__(self, server: Server, mediator: 'Mediator'):
#         """
#
#         Parameters
#         ----------
#         server
#             Server name
#         """
#         self.server = server
#         self.mediator = mediator
#
#     @abstractmethod
#     def send_message(self, destination: Server, **kwargs) -> t.Any:
#         ...
#
#     @abstractmethod
#     async def async_send_message(self, destination: Server, **kwargs) -> t.Any:
#         ...
#
#     @abstractmethod
#     def dispatch_message(self, msg: dict) -> t.Any:
#         ...


class OperationFactory:
    _factories: t.Dict[ActionType, t.Type[dpl.IOperationEncapsulation]] = {}

    def __init__(self):
        for at in ActionType:
            try:
                self._factories.update({at: dpl.__dict__[at.name.capitalize() + 'Operation']})
            except KeyError:
                NotImplementedError(f"{at.name.capitalize() + 'Operation'} not implemented")

    def create_operation(self, step: Step) -> dpl.IOperationEncapsulation:
        cls = self._factories[step.type]

        return cls(code=step.code, expected_output=step.expected_output, expected_rc=step.expected_rc,
                   system_kwargs=step.system_kwargs)
