import random
import typing as t

from ..interfaces.entity import Id as IdType


class Id:
    """
    Descriptor describing identity of an entity.
    """

    def __init__(self, *field_names, auto_fill=True,
                 factory: t.Callable[[], t.Any] = lambda: random.randint(1, 1000000),
                 ):
        """
        Given field_names are fields of the owner to build an identity key.
        No `field_names` mean that id has to be auto-generated, not natural.
        """
        self.field_names = field_names or ()
        self.auto_fill = auto_fill
        self.factory = factory

    def __set_name__(self, owner, name):
        self.owner = owner
        self.name = name

    def __set__(self, instance, value):
        if not self.field_names and instance.__dict__.get(self.name) is None:
            instance.__dict__[self.name] = value
        else:
            raise AttributeError('Frozen attribute')

    def __get__(self, instance, owner):
        if not instance:
            return self
        if not self.field_names:
            if instance.__dict__.get(self.name) is None and self.auto_fill:
                value = self.factory()
                setattr(instance, self.name, value)
            else:
                value = instance.__dict__.get(self.name)
            return value
        return tuple(getattr(instance, v) for v in self.field_names)


class Entity:
    """
    Entity is a business logic pattern: it is thought to have a set of fields and methods
    that embody some knowledge about the domain.
    * Entity class is structured, which means that some relation to other entity is represented by
      concrete reference to the other object.
    * Entity (and an aggregate root especially) should represent complex data and shouldn't
      be normalized.
    """
    __id__: IdType = Id()

    def __init__(self, **kwargs):
        """
        Sets the ID if specified
        """
        if not type(self).__id__.field_names:
            self.__id__ = kwargs.get('id')

    @property
    def id(self) -> IdType:
        """
        Defines access to the primary key of the object.
        NB: some of the DAOs will use some non-standard data type as primary key or a composite
        of values.
        """
        return self.__id__

    def __eq__(self, other) -> bool:
        """Entity is identified by the Id."""
        return isinstance(other, self.__class__) and other.id == self.id

    def __hash__(self):
        return hash(self.id)
