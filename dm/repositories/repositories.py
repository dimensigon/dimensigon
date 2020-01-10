import ipaddress
import typing as t
import uuid

from dm.domain.catalog_manager import CatalogManager
from dm.domain.entities import ActionTemplate, Orchestration, Step, Server, Service
from dm.domain.entities.catalog import Catalog
from dm.domain.entities.log import Log
from dm.domain.schemas import ActionTemplateSchema, OrchestrationSchema, StepSchema, ServiceSchema, ServerSchema, \
    ExecutionSchema
from dm.domain.schemas.catalog import CatalogSchema
from dm.domain.schemas.log import LogSchema
from dm.framework.data.predicate import where
from dm.framework.domain import Repository
from dm.framework.interfaces.entity import Id, Entity
from dm.framework.utils.dependency_injection import Inject
from dm.utils.datamark import FIELD
from domain.entities.dimension import Dimension
from domain.schemas.dimension import DimensionSchema
from web import db


class DataMarkRepo(Repository[Id, Entity]):
    catalog: CatalogManager = Inject()

    def add(self, entity: Entity) -> Id:
        if not (hasattr(entity, FIELD) and getattr(entity, FIELD)):
            self.catalog.set_data_mark(entity)
        return super().add(entity)

    def update(self, entity: Entity) -> t.Optional[Id]:
        # TODO check if entity has updated fields
        self.catalog.set_data_mark(entity, force=True)
        return super().update(entity)


class ActionTemplateRepo(DataMarkRepo[str, ActionTemplate]):
    schema = ActionTemplateSchema
    upgradable = True


class OrchestrationRepo(DataMarkRepo[str, Orchestration]):
    schema = OrchestrationSchema
    upgradable = True


class StepRepo(DataMarkRepo[str, Step]):
    schema = StepSchema
    upgradable = True


class ServerRepo:

    def get_neighbours(self):
        query = db.Server.filter(mesh_best_route='[]').filter(where('id') != str(interactor.server.id))
        servers = []
        for dto in query.all():
            servers.append(self.schema.construct(dto))
        return servers

    def get_not_neighbours(self):
        from dm.web import interactor
        query = self.dao.filter(where('route') != '[]').filter(where('id') != str(interactor.server.id))
        servers = []
        for dto in query.all():
            servers.append(self.schema.construct(dto))
        return servers


class ServiceRepo(DataMarkRepo[str, Service]):
    schema = ServiceSchema
    upgradable = True


class ExecutionRepo(Repository):
    schema = ExecutionSchema


class LogRepo(Repository[str, Log]):
    schema = LogSchema
    upgradable = True


class CatalogRepo(Repository[str, Catalog]):
    schema = CatalogSchema


class DimensionRepo(Repository[str, Dimension]):
    schema = DimensionSchema

    def get_by_name(self, name):
        query = self.dao.filter((where('name') == name))
        data = query.one()
        return self.schema.construct(data)