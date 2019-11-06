import typing as t

from flask import jsonify, request
from flask_restful import abort

from dm.domain.entities import Orchestration
from dm.domain.schemas.orchestration import OrchestrationSchemaNested
from dm.framework.interfaces.entity import Id
from dm.utils.helpers import str_to_key
from dm.web.api_1_0.resources.base import BaseSingleResource, BaseListResource


class OrchestrationResource(BaseSingleResource):
    __entity__ = Orchestration

    def get(self, id: Id):
        if 'include' in request.args:
            include = request.args.get('include')
            if include == 'steps':
                schema = OrchestrationSchemaNested()
                orchestration = self.repo.find(id)
                data = schema.deconstruct(orchestration)
                return data
            else:
                return abort(404, message=f"Bad include type '{include}'")
        return super().get(id)


class OrchestrationListResource(BaseListResource):
    __entity__ = Orchestration

    def get(self):
        if 'include' in request.args:
            include = request.args.get('include')
            if include == 'steps':
                schema = OrchestrationSchemaNested()
                data = []
                for orchestration in self.repo.all():
                    return schema.deconstruct(orchestration)
            else:
                return abort(404, message=f"Bad include type '{include}'")
        else:
            return super().get()
