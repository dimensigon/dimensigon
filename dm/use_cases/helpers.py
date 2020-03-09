import typing as t

from dm.domain.entities import Scope, Server


def get_servers_from_scope(scope: Scope, *args, **kwargs) -> t.List[Server]:
    """
    Returns the servers to lock for the related scope

    Parameters
    ----------
    scope: Scope

    Returns
    -------

    """
    if scope == scope.CATALOG:
        servers = Server.query.all()
    elif scope == scope.UPGRADE:
        servers = Server.get_current()
    else:
        servers = []
    return servers
