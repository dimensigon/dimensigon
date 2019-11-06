import itertools
import typing as t

from attrdict import AttrDict

from .entity import Id, Ids

Kwargs = t.Dict[str, t.Any]
BatchOfKwargs = t.Sequence[Kwargs]


# class Kwargs(Kwargs):
#     """
#     Represents a Data Transfer Object retrieved from some Data Access Object.
# 
#     DTO is a `dict`-like object with some identity (a property) set by the persistence layer
#     lying beneath the DAO. DTOs carry de-structured and normalized data of some kind of domain
#     entity, intended to be put into the persistence layer.
#     """
# 
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.__id__ = None
#         if len(args) == 1 and isinstance(args[0], Kwargs):
#             self.__id__ = args[0].id
#         elif 'id' in self:
#             self.__id__ = self.pop('id')
#         elif 'id_' in self:
#             self.__id__ = self.pop('id_')
# 
#     @property
#     def id(self):
#         return self.__id__
# 
#     def __eq__(self, other):
#         if isinstance(other, self.__class__):
#             if self.__id__ is None and other.__id__ is None:
#                 return tuple(sorted(self.keys())) == tuple(sorted(other.keys()))
#             else:
#                 return self.__id__ == other.__id__
# 
#     def __hash__(self):
#         return hash(self.__id__ or tuple(sorted(self.keys())))
# 
#     def to_dict(self, dump_only: t.Sequence[str] = None, exclude_only: t.Sequence[str] = None):
#         """Converts the DTO to a dict object
# 
#         Parameters
#         ----------
#         dump_only:
#             sequence with all fields to be dumped. If None, all fields will be dumped including id
#         exclude_only:
#             sequence with all fields MUST NOT be dumped. If None, all fields will be dumped including id
#         """
#         dump_only = dump_only or ()
#         exclude_only = exclude_only or ()
#         dumped = dict(id=self.id)
#         data = {k: v for k, v in self.items() if (k in dump_only or dump_only is ()) and k not in exclude_only}
#         dumped.update(data)
#         return dumped


BatchOfKwargs = t.TypeVar('BatchOfKwargs', t.Iterable[Kwargs], t.Sized)


class IPredicate:
    """Interface of logical predicate."""


class IQueryChain(t.Iterable[Kwargs], t.Sized, t.Generic[Id]):
    """
    Technical detail of chaining queries.

    A proxy for a query interface of DAO, gathering lazy evaluated queries
    (ie. filter, sort, aggregate, etc) to call owning DAO to resolve them when non-lazy
    (ie. get, exists, count, update, etc) is called.
    """

    # TODO lazy queries: order_by, aggregate, annotate
    # TODO evaluating queries: slicing

    # lazy queries

    def filter(self, predicate: IPredicate) -> 'IQueryChain':
        """
        Filters out objects by the predicate specifying conditions that they
        should met. Can be chained via `IQueryChain` helper class.
        """
        raise NotImplementedError

    def filter_by(self, id_: Id = None, ids: Ids = None) -> 'IQueryChain':
        """
        Filters objects by a single id or a iterable of ids.

        :raises: InvalidQueryError if:
            * both `id_` and `ids` arguments are defined
            * or the query is already filtered by id
        """
        raise NotImplementedError

    # evaluating queries

    def __iter__(self) -> t.Iterator:
        """Yields values"""
        raise NotImplementedError

    def one(self) -> t.Optional[Kwargs]:
        """Returns one object for the current QueryChain."""
        raise NotImplementedError

    def one_or_none(self) -> t.Optional[Kwargs]:
        """Returns one object for the current QueryChain."""
        raise NotImplementedError

    def all(self) -> t.List[Kwargs]:
        """Returns all objects for the current QueryChain"""
        raise NotImplementedError

    def get(self, id_: Id) -> t.Optional[Kwargs]:
        """Returns object of given id, or None iff not present."""
        raise NotImplementedError

    def exists(self) -> bool:
        """Returns whether any object specified by the query exist."""
        raise NotImplementedError

    def __len__(self) -> int:
        """Same as `count`."""
        raise NotImplementedError

    def count(self) -> int:
        """
        Counts objects filtering them out by the query specifying conditions that they
        should met.
        """
        raise NotImplementedError

    # evaluating commands

    def update(self, *args, **kwargs) -> Ids:
        """
        Updates all objects specified by the query with given update.
        """
        raise NotImplementedError

    def remove(self) -> Ids:
        """
        Removes all objects specified by the query from the collection.
        """
        raise NotImplementedError


class IDao(t.Generic[Id]):
    """
    Interface for Data Access Object. Describes an abstraction over any kind
    of collections of objects of data: both relational database's tables and
    non-relational document sets, etc.
    """

    # lazy queries

    def all(self) -> IQueryChain:
        """
        Returns a query chain representing all objects.

        Useful to explicitly denote counting, updating or removing all objects.
        """
        raise NotImplementedError

    def filter(self, predicate: IPredicate) -> IQueryChain:
        """
        Filters out objects by the predicate specifying conditions that they
        should met.
        Can be chained with other queries via `IQueryChain` helper.
        """
        raise NotImplementedError

    def filter_by(self, id_: Id = None, ids: Ids = None) -> IQueryChain:
        """
        Filters objects by a single id or a iterable of ids.
        Can be chained with other queries via `IQueryChain` helper.

        :raises: InvalidQueryError if:
            * both `id_` and `ids` arguments are defined
            * or the query is already filtered by id
        """
        raise NotImplementedError

    # evaluating queries

    def get(self, id_: Id) -> t.Optional[Kwargs]:
        """
        Returns object of given id, or None iff not present.
        Shortcut for querying via `IDao.all`.
        """
        raise NotImplementedError

    # instant commands
    def insert(self, *args, **kwargs) -> Id:
        """
        Inserts the object into the collection.

        :returns: id of the inserted object
        """
        raise NotImplementedError

    def update(self, *args, **kwargs) -> Id:
        """
        Updates the object from the collection.

        :returns: id of the updated object
        """
        raise NotImplementedError

    def upsert(self, *args, **kwargs) -> Id:
        """
        Inserts or updates the object from the collection

        Parameters
        ----------
        args
        kwargs

        Returns
        -------
            id of the updated or inserted object
        """
        raise NotImplementedError

    def batch_insert(self, batch_kwargs: BatchOfKwargs) -> Ids:
        """
        Inserts multiple objects into the collection.

        :returns: a iterable of ids
        """
        raise NotImplementedError

    def clear(self) -> None:
        """
        Removes all items from the collection.
        """
        raise NotImplementedError
