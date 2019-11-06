import typing as t

from dm.domain.entities import Step
from dm.web.api_1_0.resources.base import BaseSingleResource, BaseListResource


class StepListResource(BaseListResource):
    __entity__ = Step

    
class StepResource(BaseSingleResource):
    __entity__ = Step
