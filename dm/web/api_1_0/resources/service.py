import typing as t

from dm.domain.entities import Service
from dm.web.api_1_0.resources.base import BaseSingleResource, BaseListResource


class ServiceListResource(BaseListResource):
    __entity__ = Service

    
class ServiceResource(BaseSingleResource):
    __entity__ = Service
