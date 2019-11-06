import typing as t
from datetime import datetime

from dm.framework.domain import Entity, Id

DataMark = t.TypeVar('DataMark', datetime, int, str)


class Catalog(Entity, t.Generic[DataMark]):
    __id__ = Id('entity')

    def __init__(self, entity: str, data_mark: DataMark, **kwargs):
        super().__init__(**kwargs)
        self.entity = entity
        self.data_mark = data_mark
