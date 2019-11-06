import typing as t

from dm.framework.data.dao import AbstractDao
from dm.framework.data.dao.abstract import QueryChain
from dm.framework.interfaces.dao import BatchOfKwargs, Kwargs
from dm.framework.interfaces.entity import Id, Ids
from dm.framework.utils.dependency_injection import Scopes, scope


@scope(Scopes.INSTANCE_NO_CONTAINER)
class DbDao(AbstractDao[Id]):

    def __init__(self, db) -> None:
        super().__init__()
        self.db = db

    def _resolve_filter(self, query_chain: QueryChain, offset: int = 0, limit: int = 0) -> t.Generator:
        pass

    def _resolve_get(self, query_chain: QueryChain, id_: Id, nullable: bool = False) -> t.Optional[Kwargs]:
        pass

    def _resolve_exists(self, query_chain: QueryChain) -> bool:
        pass

    def _resolve_count(self, query_chain: QueryChain) -> int:
        pass

    def _resolve_update(self, query_chain: QueryChain, update: Kwargs) -> Ids:
        pass

    def _resolve_remove(self, query_chain: QueryChain) -> Ids:
        pass

    def insert(self, *args, **kwargs) -> Id:
        pass

    def update(self, *args, **kwargs) -> Id:
        pass

    def batch_insert(self, dtos: BatchOfKwargs) -> Ids:
        pass

    def clear(self) -> None:
        pass

