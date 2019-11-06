import typing as t
from abc import ABC


from dm.framework.interfaces.schema import ISchema
from .dao import IDao, Kwargs
from .entity import Entity, Id


class IRepository(t.Generic[Id, Entity], ABC):
    """
    Repository serves as a collection of entites (with methods such as get, add, update, remove)
    with underlying persistence layer. Should know how to construct an instance, serialize it
    and get its id.

    Developers of repos for concrete entites are encouraged to subclass and put a meaningful
    query and command methods along the basic ones.
    """
    dao: IDao

    """
    Data Access Object which gives repo a persistence API. Its value is created
    by requiring the DAO instance related to its entity from DI container.
    """
    schema: t.ClassVar[t.Type[ISchema]]
    """Entity type collected by this repo."""

    def create(self, **kwargs: Kwargs) -> Entity:
        """
        Creates an object compatible with this repo. Uses repo's factory
        or the klass iff factory not present.

        NB: Does not inserts the object to the repo. Use `create_and_add` method for that.
        """
        raise NotImplementedError

    def add(self, entity: Entity):
        """Adds the object to the repo to the underlying persistence layer via its DAO."""
        raise NotImplementedError

    def create_and_add(self, **kwargs: Kwargs) -> Entity:
        """Creates an object compatible with this repo and adds it to the collection."""
        raise NotImplementedError

    def find(self, id_: Id) -> t.Optional[Entity]:
        """Returns object of given id or None"""
        raise NotImplementedError

    def contains(self, id_: Id):
        """Checks whether an entity of given id is in the repo."""
        raise NotImplementedError

    def update(self, entity: Entity) -> None:
        """Updates the object in the repo."""
        raise NotImplementedError

    def remove(self, entity: Entity) -> None:
        """Removes the object from the underlying persistence layer via DAO."""
        raise NotImplementedError

    def all(self) -> t.List[Entity]:
        """Retrives all entities from this repo"""
        raise NotImplementedError

