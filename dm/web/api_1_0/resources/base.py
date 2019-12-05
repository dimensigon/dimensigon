import typing as t

from flask import jsonify, request
from flask_restful import Resource, abort
from marshmallow import ValidationError

from dm.framework.domain import Entity
from dm.framework.interfaces.entity import Id
from dm.web import repo_manager
from dm.framework.interfaces.repository import IRepository
from dm.utils.helpers import key_to_str, str_to_key


class BaseResource(Resource):
    __entity__: Entity = None

    @property
    def repo(self) -> t.Optional[IRepository]:
        if repo_manager and self.__entity__:
            return eval(f'repo.{self.__entity__.__name__}Repo')
        else:
            return None


class BaseListResource(BaseResource):
    __entity__: Entity = None

    def get(self):
        schema = self.repo.schema
        # data = [(lambda d: d.update({'id': key_to_str(dto.id)}) or d)(dto.to_dict()) for dto in self.repo.all()]
        data = [schema.deconstruct(e) for e in self.repo.all()]
        return data

    def post(self):
        data = request.json
        try:
            ent = self.repo.create_and_add(**data)
        except ValidationError as e:
            return e.messages, 404
        return key_to_str(ent.id), 201


class BaseSingleResource(BaseResource):

    def get(self, id: Id):
        dto = self.repo.dao.get(id)
        if dto is None:
            abort(404, message=f"{self.__entity__.__class__.__name__} id '{id}' does not exist")
        else:
            return dto
