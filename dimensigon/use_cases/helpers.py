import datetime as dt
import typing as t

from flask import current_app
from flask_jwt_extended import create_access_token
from sqlalchemy import not_

from dimensigon import defaults
from dimensigon.domain.entities import Scope, Server
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.utils.helpers import get_now


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
    me = Server.get_current()
    if scope == scope.CATALOG:
        last_alive_ids = current_app.dm.cluster_manager.get_alive()
        if me.id not in last_alive_ids:
            last_alive_ids.append(me.id)
        all_query = Server.query.filter_by(l_ignore_on_lock=False)
        if isinstance(bypass, list):
            all_query = all_query.filter(not_(Server.id.in_([s.id for s in bypass])))
        elif isinstance(bypass, Server):
            all_query = all_query.filter_by(Server.id != bypass.id)
        n_servers = all_query.count()

        adult_query = all_query.filter(Server.created_on <= get_now() - defaults.ADULT_NODES)
        n_adult_nodes = adult_query.count()

        if n_adult_nodes == 0:
            if n_servers <= defaults.MIN_SERVERS_QUORUM:
                return all_query.filter(Server.id.in_(last_alive_ids)).order_by(
                    Server.created_on).all()
            else:
                return all_query.filter(Server.id.in_(last_alive_ids)).order_by(
                    Server.created_on).limit(defaults.MIN_SERVERS_QUORUM).all()

        elegible_query = adult_query.filter(Server.id.in_(last_alive_ids))
        n_elegible = elegible_query.count()

        if n_elegible <= defaults.MIN_SERVERS_QUORUM:
            return elegible_query.all()
        else:
            servers = elegible_query.order_by(Server.created_on).all()
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


def get_root_auth():
    return HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
