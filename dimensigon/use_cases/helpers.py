import typing as t

from flask import current_app
from flask_jwt_extended import create_access_token
from sqlalchemy import not_

from dimensigon import defaults
from dimensigon.domain.entities import Scope, Server, User
from dimensigon.network.auth import HTTPBearerAuth


def get_servers_from_scope(scope: Scope, bypass: t.Union[t.List[Server], Server] = None) -> t.List[Server]:
    """
    Returns the servers to lock for the related scope

    Parameters
    ----------
    scope: Scope

    Returns
    -------

    """
    quorum = []
    if scope == scope.CATALOG:
        q = Server.query.filter_by(l_ignore_on_lock=False).filter(
            Server.id.in_(current_app.cluster.get_alive())).order_by(
            Server.created_on)
        if isinstance(bypass, list):
            q = q.filter(not_(Server.id.in_([s.id for s in bypass])))
        elif isinstance(bypass, Server):
            q = q.filter_by(Server.id != bypass.id)
        servers = q.all()
        if len(servers) < defaults.MIN_SERVERS_QUORUM:
            return servers
        else:
            cost_dict = {}
            for server in servers:
                if server.route and server.route.cost is not None:
                    if server.route.cost not in cost_dict:
                        cost_dict[server.route.cost] = []
                    cost_dict[server.route.cost].append(server)
            if len(cost_dict) > defaults.MIN_SERVERS_QUORUM:
                for v in cost_dict.values():
                    v.sort(key=lambda x: (x.last_modified_at, x.name))
                    quorum.append(v[0])
            else:
                quorum.extend(servers[0:defaults.MIN_SERVERS_QUORUM])
            me = Server.get_current()
            if me not in quorum:
                quorum.append(me)
    elif scope == scope.UPGRADE:
        quorum = Server.get_current()
    return quorum


def get_auth_root():
    return HTTPBearerAuth(create_access_token(User.get_by_user('root').id))
