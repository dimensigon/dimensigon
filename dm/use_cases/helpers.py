import typing as t

from flask_jwt_extended import create_access_token

from dm.domain.entities import Scope, Server, User
from dm.web.network import HTTPBearerAuth


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


def get_auth_root():
    return HTTPBearerAuth(create_access_token(User.get_by_user('root').id))
