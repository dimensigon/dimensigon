import threading
import typing as t
from datetime import datetime

from dm.domain.entities.catalog import DataMark, Catalog
from dm.domain.exceptions import CatalogError

from dm.utils import Singleton
from dm.utils.helpers import get_now
from dm.utils.datamark import FIELD as DATAMARK_FIELD

if t.TYPE_CHECKING:
    from dm.framework.interfaces.entity import Id
    from dm.framework.domain import Entity


class CatalogManager(t.Generic[DataMark]):
    __metaclass__ = Singleton

    def __init__(self, type_: t.Type[DataMark], format_='%Y%m%d%H%M%S%f'):
        assert type_ in (int, str, datetime)
        self.type = type_
        self.get_all = None
        self.get = None
        self.save = None
        self._mutex = threading.Lock()
        self._entities: t.List[str] = []
        self._data_mark: t.List[DataMark] = []
        self._bypass = False
        self.__format = format_

    @property
    def format(self):
        return self.__format

    def set_catalog(self, get_all: t.Callable[..., t.List[Catalog]], get: t.Callable[['Id'], Catalog],
                    save: t.Callable[[Catalog], None]) -> None:
        if not self.get_all:
            self.get_all = get_all
            self.get = get
            self.save = save

            for catalog in self.get_all():
                if catalog.entity in self._entities:
                    idx = self._entities.index(catalog.entity)
                    if catalog.data_mark > self._data_mark[idx]:
                        self._data_mark[idx] = catalog.data_mark
                else:
                    self._entities.append(catalog.entity)
                    self._data_mark.append(catalog.data_mark)

    def decode_data(self, data: datetime):
        if issubclass(self.type, int):
            return int(data.strftime(self.format))
        elif issubclass(self.type, str):
            return data.strftime(self.format)
        elif issubclass(self.type, datetime):
            return data

    def encode_data(self, data: DataMark):
        if isinstance(data, (int, str)):
            return datetime.strptime(str(data), self.format)
        elif isinstance(data, datetime):
            return data
        else:
            raise ValueError('Invalid data type')

    def generate_data_mark(self) -> DataMark:
        return self.decode_data(get_now())

    def set_data_mark(self, entity: 'Entity', force=False):
        """

        Parameters
        ----------
        entity:
            entity to set the data mark

        Returns
        -------
        t.Optional[int]:
            returns the new data_mark or None if
        """
        cls_name = type(entity).__name__
        with self._mutex:
            if not force:
                dm = entity.__dict__.get(DATAMARK_FIELD, self.generate_data_mark()) or self.generate_data_mark()
            else:
                dm = self.generate_data_mark()

            try:
                idx = self._entities.index(cls_name)
            except ValueError:
                self._entities.append(cls_name)
                self._data_mark.append(dm)
            else:
                self._data_mark[idx] = max(self._data_mark[idx], dm)

            entity.__dict__[DATAMARK_FIELD] = dm

    def save_catalog(self) -> None:
        if self.get is None:
            raise CatalogError('Must call set_catalog first')
        for idx in range(len(self._entities)):
            c = Catalog(entity=self._entities[idx], data_mark=self._data_mark[idx])
            self.save(c)

    def update_data_mark(self, entity_name: str, data_mark: DataMark):
        """Updates the current data mark in the registry
        Parameters
        ----------
        entity_name:
            name entity to check if data_mark should be updated
        data_mark:
            data mark to update
        """
        try:
            idx = self._entities.index(entity_name)
        except ValueError as e:
            raise ValueError(f"'{entity_name}' is not in the catalog") from e
        self._data_mark[idx] = max(self.encode_data(data_mark), self._data_mark[idx])

    @property
    def max_data_mark(self) -> t.Optional[DataMark]:
        try:
            return max(self._data_mark)
        except ValueError:
            return None
