import typing as t


Id = t.TypeVar('Id', int, str, t.Tuple[t.Union[str, int], ...])
Ids = t.Sequence[Id]
Entity = t.TypeVar('Entity')

