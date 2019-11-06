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


class ServerRepo(DataMarkRepo[str, Server]):
    schema = ServerSchema
    upgradable = True

    def get_by_ip_or_name(self, ip_or_name, port=None):
        ip = None
        name = None
        try:
            ip = ipaddress.ip_address(ip_or_name)
        except ValueError:
            name = ip_or_name
        query = self.dao.filter((where('ip') == ip) if ip else (where('name') == name))
        if port:
            query = query.filter(where('port') == port)
        data = query.one()
        return self.schema.construct(data)


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