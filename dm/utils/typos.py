import typing as t


Params = t.NewType('Params', t.Union[t.Dict['str', t.Any], t.ChainMap])

Callback = t.Tuple[t.Callable[[], None], t.Tuple, t.Dict]

Priority = t.TypeVar('T')
