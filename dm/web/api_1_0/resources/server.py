import typing as t

from dm.domain.entities import Server
from dm.web.api_1_0.resources.base import BaseSingleResource, BaseListResource


class ServerListResource(BaseListResource):
    __entity__ = Server

    
class ServerResource(BaseSingleResource):
    __entity__ = Server
