import copy
import typing as t
from itertools import count

from .abstract import (
    AbstractDao, QueryChain)
from ...exceptions import *
from ...interfaces.dao import (
    Kwargs,
    BatchOfKwargs,
    Id,
    Ids)
from ...utils.dependency_injection import Scopes, scope


@scope(Scopes.SINGLETON_NO_CONTAINER)
class InMemoryDao(AbstractDao[Id]):

    def __init__(self, initial_content: t.Union[BatchOfKwargs, BatchOfKwargs] = None):
        self._register: t.Dict[int, Kwargs] = {}
        self._id_generator = count(1)
        if initial_content:
            self.batch_insert(initial_content)
            if isinstance([id_ for id_ in self._register.keys()][0], int):
                self._id_generator = count(max(self._register.keys()) + 1, 1)

    @property
    def get_id(self) -> Id:
        return self._get_id()

    def _get_id(self) -> Id:
        return next(self._id_generator)

    def _resolve_filter(self, query_chain: QueryChain, offset: int = 0, limit: int = 0) -> t.Generator:
        if query_chain._filters:
            filter_ = query_chain._reduced_filter
            filtered: t.Generator = (
                (id_, data) for id_, data in self._register.items()
                if filter_(data)
            )
        else:
            filtered = ((id_, data) for id_, data in self._register.items())
        if query_chain._ids:
            filtered = ((id_, data) for id_, data in filtered if id_ in query_chain._ids)
        # return [kwargs for kwargs in filtered if kwargs]
        i = 0
        yielded = 0
        while yielded < limit or limit == 0:
            if i >= offset:
                yielded += 1
                try:
                    id_, data = next(filtered)
                    yield dict(data)
                except StopIteration:
                    return
            else:
                next(filtered)
            i += 1

    def _resolve_get(self, dtos: BatchOfKwargs, id_: Id, nullable: bool = False) -> t.Optional[Kwargs]:
        result = next((dto for dto in dtos if dto.get('id') == id_), None)
        if result is not None:
            return copy.deepcopy(result)
        elif nullable:
            return
        raise NotFound(id_)

    def _resolve_exists(self, query_chain: QueryChain) -> bool:
        filtered = list(self._resolve_filter(query_chain))
        return bool(filtered)

    def _resolve_count(self, query_chain: QueryChain) -> int:
        filtered = list(self._resolve_filter(query_chain))
        return len(filtered)

    def _resolve_update(self, query_chain: QueryChain, update: Kwargs) -> Ids:
        ids = []
        for kwargs in self._resolve_filter(query_chain):
            self._register[kwargs.get('id')].update(update)
            ids.append(kwargs.get('id'))
        return ids

    def _resolve_remove(self, query_chain: QueryChain) -> Ids:
        if query_chain._is_trivial:
            raise UnrestrictedRemove
        dtos_to_remove = [
            kwargs.get('id')
            for kwargs in self._resolve_filter(query_chain)
        ]
        for id_ in dtos_to_remove:
            self._register.pop(id_)
        return dtos_to_remove

    def insert(self, *args, **kwargs) -> Id:
        data = dict(*args, **kwargs)
        id_ = data.get('id')
        if id_ is None:
            id_ = self._get_id()
            data.update(id=id_)
        if id_ in self._register:
            raise IdAlreadyExists(id_)
        self._register[id_] = data
        return id_

    def update(self, *args, **kwargs) -> Id:
        data = dict(*args, **kwargs)
        self.filter_by(id_=data.get('id')).update(data)
        return data.get('id')

    def upsert(self, *args, **kwargs) -> Id:
        try:
            return self.insert(*args, **kwargs)
        except IdAlreadyExists:
            return self.update(*args, **kwargs)

    def batch_insert(self, batch_dto: t.Union[BatchOfKwargs, BatchOfKwargs]) -> Ids:
        return tuple(self.insert(dto) for dto in batch_dto)

    def clear(self) -> None:
        self._register.clear()
