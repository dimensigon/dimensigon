import typing as t

from returns.result import safe

if t.TYPE_CHECKING:
    from dm import Server
    from dm.use_cases import Scope


@safe
def get_servers_from_scope(scope: 'Scope', *args, **kwargs) -> t.List['Server']:
    """
    Returns the servers to lock for the related scope

    Parameters
    ----------
    scope: Scope

    Returns
    -------

    """
    # TODO implement get servers from scope
    scope

    return list()
