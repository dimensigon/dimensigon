import typing as t

from .dao import Kwargs
from .entity import Entity


class ISchema(t.Generic[Entity]):
    """
    A prototype serialization/validation class, designed to:
      * support dataclasses as entities
      * deconstruct specified fields (all dataclass fields by default)
    """

    def construct(self, **dto: Kwargs) -> Entity:
        """
        Defines a way to construct (aka deserialize) an entity from data.
        """
        raise NotImplemented

    def deconstruct(self, entity: Entity) -> Kwargs:
        """
        Defines a way to deconstruct (aka serialize) an entity to dto
        Parameters
        ----------
        entity

        Returns
        -------

        """
        raise NotImplemented
