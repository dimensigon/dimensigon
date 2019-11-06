import typing as t

from dm.domain.entities import ActionTemplate
from dm.web.api_1_0.resources.base import BaseSingleResource, BaseListResource


class ActionTemplateListResource(BaseListResource):
    __entity__ = ActionTemplate


class ActionTemplateResource(BaseSingleResource):
    __entity__ = ActionTemplate
