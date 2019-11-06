import typing as t

from marshmallow import Schema as MSchema, post_dump, pre_load, post_load
from marshmallow.utils import INCLUDE

from dm.framework.domain import fields, Entity
from dm.framework.exceptions import NoContainerProvided
from dm.framework.interfaces.dao import IDao, Kwargs
from dm.framework.interfaces.entity import Entity as EntityType, Id, Ids
from dm.framework.interfaces.schema import ISchema
from dm.framework.utils.dependency_injection import Container, g_container
from dm.framework.utils.functools import reify


def get_key(wanted_fields: t.Tuple, kwargs: t.Mapping):
    if wanted_fields:
        id_ = tuple(kwargs.get(f) for f in wanted_fields)
    else:
        try:
            id_ = kwargs['id']
        except KeyError:
            try:
                id_ = kwargs['id_']
            except KeyError:
                id_ = None
    return id_


class Schema(MSchema, ISchema, t.Generic[EntityType]):
    __entity__: t.ClassVar[t.Type[EntityType]]
    __container__: t.ClassVar[Container]

    class Meta:
        unknown = INCLUDE

    def __new__(cls, *args, **kwargs):
        if not cls.__entity__ or not issubclass(cls.__entity__, Entity):
            raise AttributeError('No entity specified')
        return super().__new__(cls)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self._nested_objects = {}  # buffer data for nested objects

    @classmethod
    def set_container(cls, container):
        cls.__container__ = container

    # @post_dump(pass_original=True)
    # def get_ids(self, data, original_data, **kwargs) -> Dto:
    #     dto = Dto(data)
    #     dto.__id__ = original_data.id
    #     return dto

    @staticmethod
    def fetch_data(field_class, id_or_ids: t.Union[Id, Ids]):
        entity = field_class.schema.entity
        container = field_class.schema.__container__
        if not isinstance(container, Container):
            # try with the global container
            if g_container:
                container = g_container
        if not isinstance(container, Container):
            raise NoContainerProvided(field_class.schema.__class__.__name__)
        dao: IDao = container.find_by_interface(interface=IDao, qualifier=entity)
        if field_class.many:
            nested_data = [dao.get((id_,) if entity.__id__.field_names and not isinstance(id_, tuple) else id_)
                           for id_ in id_or_ids]
        else:
            nested_data = dao.get(
                id_=(id_or_ids,) if entity.__id__.field_names and not isinstance(id_or_ids, tuple) else id_or_ids)
        return nested_data

    @pre_load
    def gather_nested_objects(self, data, **kwargs):
        if data:
            for field, field_class in self.nested_fields.items():
                if isinstance(data, t.Dict):
                    id_or_ids = data.get(field)
                else:
                    id_or_ids = data
                if isinstance(field_class, (fields.PluckEntity, fields.Pluck)):
                    nested_data = self.fetch_data(field_class, id_or_ids)
                elif isinstance(field_class, fields.Mapping):
                    nested_data = {}
                    for key, value in data[field].items():
                        if isinstance(field_class.key_field, fields.Pluck):
                            key_nested = self.fetch_data(field_class.key_field, key)
                        else:
                            key_nested = key
                        if isinstance(field_class.value_field, fields.Nested):
                            value_nested = self.fetch_data(field_class.value_field, value)
                        else:
                            value_nested = value
                        nested_data.update({key_nested: value_nested})
                else:
                    if field_class.many:
                        id_or_ids = [get_key(field_class.schema.entity.__id__.field_names, id_) for id_ in
                                     id_or_ids or []]
                    else:
                        id_or_ids = get_key(field_class.schema.entity.__id__.field_names, id_or_ids)
                    nested_data = self.fetch_data(field_class, id_or_ids)
                if isinstance(data, t.Dict):
                    data[field] = nested_data
                else:
                    data = nested_data
        return data

    @post_load
    def make_entity(self, data, **kwargs):
        return self.entity(**data)

    @property
    def entity(self):
        return self.__entity__

    @reify
    def nested_fields(self):
        return {field: field_class for field, field_class in self.fields.items() if
                isinstance(field_class, fields.Nested) or (isinstance(field_class, fields.Mapping) and (
                        isinstance(field_class.key_field, fields.Nested) or isinstance(field_class.value_field,
                                                                                       fields.Nested)))}

    def construct(self, dto: Kwargs, **kwargs) -> EntityType:
        # noinspection PyTypeChecker
        return self.load(data=dto, **kwargs)

    def deconstruct(self, entity: EntityType, **kwargs) -> Kwargs:
        # noinspection PyTypeChecker
        return self.dump(obj=entity, **kwargs)
