import typing as t
from dataclasses import dataclass
from enum import Enum

import dm.use_cases.deployment as dpl
from dm.domain.entities import ActionType
from dm.domain.entities.orchestration import Step



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
        return self.source + '.' + self.destination + '.' + str(self.id)


class Scope(Enum):
    UPGRADE = 10
    ORCHESTRATION = 30
    CATALOG = 40

    def __lt__(self, other):
        return self.value < other.value


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
