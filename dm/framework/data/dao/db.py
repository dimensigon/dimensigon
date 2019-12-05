import copy
import sqlite3
import typing as t

from dm.framework.data.dao import AbstractDao
from dm.framework.data.dao.abstract import QueryChain
from dm.framework.exceptions import NotFound, UnrestrictedRemove, IdAlreadyExists
from dm.framework.interfaces.dao import BatchOfKwargs, Kwargs
from dm.framework.interfaces.entity import Id, Ids
from dm.framework.utils.dependency_injection import Scopes, scope



@scope(Scopes.INSTANCE_NO_CONTAINER)
class DbDao(AbstractDao[Id]):
    """
    Parameters
    ----------
    table:
        table to fetch, update, insert and delete data
    *args:
        args passed to sqlite3.connect
    **kwargs:
        kwargs passed to sqlite3.connect
    """

    def __init__(self, table, db) -> None:
        super().__init__()
        self.table = table
        self.db = db


    @property
    def con(self):
        return self.db

    def _resolve_filter(self, query_chain: QueryChain, offset: int = 0, limit: int = 0) -> t.Generator:
        query = f"select * from {self.table}"
        if query_chain._ids:
            query = query + " where id " + ("in (%s)" % ','.join(
                ['?' for _ in range(len(query_chain._ids))]) if len(query_chain._ids) > 1 else " = ?")
        filtered: t.Generator = ((data['id'], data) for data in
                                 self.con.execute(query, tuple(query_chain._ids or ())))

        if query_chain._filters:
            filter_ = query_chain._reduced_filter
            filtered: t.Generator = (((id_, data) for id_, data in filtered if filter_(data)))

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
        keys = []
        values = []
        for k, v in update.items():
            keys.append(k)
            values.append(v)
        sql = f"UPDATE {self.table} SET " + ' '.join([str(k) + " == ?" for k in keys]) + " WHERE id = ?"
        for kwargs in self._resolve_filter(query_chain):
            ids.append(kwargs.get('id'))
        self.con.executemany(sql, [tuple(values + [id_]) for id_ in ids])
        return ids

    def _resolve_remove(self, query_chain: QueryChain) -> Ids:
        if query_chain._is_trivial:
            raise UnrestrictedRemove
        dtos_to_remove = [
            kwargs.get('id')
            for kwargs in self._resolve_filter(query_chain)
        ]
        sql = f"delete from {self.table} where id = ?"
        self.con.executemany(sql, [(x,) for x in dtos_to_remove])
        return dtos_to_remove

    def insert(self, *args, **kwargs) -> Id:
        data = dict(*args, **kwargs)
        sql = f"INSERT INTO {self.table} (" + ', '.join(data.keys()) + ") VALUES (" + \
              ','.join(['?' for _ in range(len(data.keys()))]) + ")"
        try:
            rowid = self.con.execute(sql, tuple(data.values())).lastrowid
        except sqlite3.IntegrityError as e:
            raise IdAlreadyExists from e
        return self.con.execute(f"SELECT id FROM {self.table} WHERE rowid = ?", (rowid,)).fetchone().get('id')

    def update(self, *args, **kwargs):
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
        pass
