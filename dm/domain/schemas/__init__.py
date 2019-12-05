import inspect
import sys

from dm.framework.domain.schema import Schema
from .action_template import ActionTemplateSchema
from .dimension import DimensionSchema
from .execution import ExecutionSchema
from .orchestration import OrchestrationSchema, StepSchema, OrchestrationSchemaNested
from .server import ServerSchema
from .service import ServiceSchema
from .user import UserSchema

__all__ = [
    'ActionTemplateSchema',
    'DimensionSchema',
    'ExecutionSchema',
    'OrchestrationSchema',
    'OrchestrationSchemaNested',
    'StepSchema',
    'ServerSchema',
    'ServiceSchema',
    'UserSchema',
    'set_container'
]


def set_container(container):
    for name, cls in inspect.getmembers(sys.modules[__name__],
                                        lambda p: inspect.isclass(p) and issubclass(p,
                                                                                    Schema) and p.__name__ != "Schema"):
        cls.set_container(container)
