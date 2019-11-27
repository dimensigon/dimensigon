import inspect
import typing as t

from dm.framework.interfaces.entity import Entity
from .schema import Schema
import dm.framework.exceptions as exc
from ..interfaces.dao import IDao, Kwargs
from ..interfaces.repository import Id, IRepository
from ..utils.dependency_injection import Container, Scopes, scope
from ..utils.functools import reify


@scope(Scopes.SINGLETON)
class Repository(IRepository[Id, Entity]):
    """
    Repository serves as a collection of entites (get, add, update, remove) with underlying
    persistence layer. Via its schema class, it knows how to construct an instance of the entity,
    serialize it and get its id.

    Developers of repos for concrete entites are encouraged to subclass and put a meaningful
    query and command methods along the basic ones.

    Parameters
    ----------
    container:
        container with the DAO
    schema:
        optional schema if not set during class definition
    upgradable:
        optional parameter that tells the Catalog to update
    """
    schema: t.ClassVar[t.Type[Schema]]

    def __init__(self, container: Container, schema: t.Type[Schema] = None):
        self.container = container

        self.schema = schema or self.schema
        if not self.schema:
            raise exc.NoSchemaDefined
        if inspect.isclass(self.schema):
            self.schema = self.schema()

    @reify
    def dao(self) -> IDao:
        """
        Data Access Object which gives repository a persistence API. Its value is created
        by requiring it from DI container in the context of the entity given for this repo.
        """
        return self.container.find_by_interface(interface=IDao, qualifier=self.schema.__entity__)

    @property
    def entity(self):
        """Proxy to entity class defined by the schema."""
        return self.schema.entity

    def create(self, dto: Kwargs) -> Entity:
        """
        Creates an object compatible with this repo.

        NB: Does not inserts the object to the repo. Use `create_and_add` method for that.
        """
        return self.schema.construct(dto, partial=('id',))

    def add(self, entity: Entity) -> Id:
        """Adds the object to the repo to the underlying persistence layer via its DAO."""
        dto = self.schema.deconstruct(entity)
        try:
            id_ = self.dao.insert(dto)
        except exc.IdAlreadyExists as e:
            e.args = (f"{self.entity.__name__}('{e.args[0]}')",)
            raise e from e

        # should the repository set the ID?
        try:
            entity.__id__ = id_
        except AttributeError:
            pass
        return id_

    def update(self, entity: Entity) -> t.Optional[Id]:
        """Updates the object from the repo"""
        dto = self.schema.deconstruct(entity)
        id_serialized = self.schema.fields['id'].serialize('id', {'id': entity.id})
        ids = self.dao.filter_by(id_=id_serialized).update(dto)
        return ids[0] if len(ids) > 0 else None

    def create_and_add(self, dto: Kwargs) -> Entity:
        """Creates an object compatible with this repo and adds it to the collection."""
        entity = self.create(dto)
        self.add(entity)
        return entity

    def find(self, id_: Id) -> t.Optional[Entity]:
        """Returns object of given id or None."""
        id_serialized = self.schema.fields['id'].serialize('id', {'id': id_})
        dto = self.dao.get(id_serialized)
        if not dto:
            raise exc.NotFound(id_, self.entity)
        entity = self.schema.construct(dto)
        return entity

    def contains(self, id_: Id) -> bool:
        """Checks whether an entity of given id is in the repo."""
        id_serialized = self.schema.fields['id'].serialize('id', {'id': id_})
        return self.dao.filter_by(id_=id_serialized).exists()

    def remove(self, entity: Entity) -> None:
        """Removes the object from the underlying persistence layer via DAO."""
        if entity.id is None:  # entity hasn't been added yet
            raise exc.EntityNotYetAdded(entity)
        id_serialized = self.schema.fields['id'].serialize('id', {'id': entity.id})
        result = self.dao.filter_by(id_=id_serialized).remove()
        if not result:  # entity hasn't been found in the DAO
            raise exc.NotFound(entity.id, entity)

    def __iter__(self) -> t.Iterator[Entity]:
        for dto in self.dao.all():
            yield self.schema.construct(dto)

    def all(self) -> t.List[Entity]:
        return [self.schema.construct(dto) for dto in self.dao.all()]
