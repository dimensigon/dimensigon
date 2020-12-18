import datetime as dt
import logging
import re
import sys
import threading
import traceback
import typing as t
from contextlib import contextmanager
from json import JSONEncoder

from flask import current_app, request
from flask_jwt_extended import create_access_token, get_jwt_identity
from flask_sqlalchemy import BaseQuery
from sqlalchemy import not_
from sqlalchemy.orm import sessionmaker

from dimensigon import defaults
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.utils.asyncio import run
from dimensigon.utils.helpers import is_iterable_not_string, get_now
from dimensigon.utils.typos import Id
from dimensigon.web.errors import EntityNotFound, NoDataFound

logger = logging.getLogger(__name__)

if t.TYPE_CHECKING:
    from dimensigon.domain.entities import Server, Scope


class BaseQueryJSON(BaseQuery):
    """SQLAlchemy :class:`~sqlalchemy.orm.query.Query` subclass with convenience methods for querying in a web application.

    This is the default :attr:`~Model.query` object used for models, and exposed as :attr:`~SQLAlchemy.Query`.
    Override the query class for an individual model by subclassing this and setting :attr:`~Model.query_class`.
    """

    def get_or_raise(self, ident, description=None):
        """Like :meth:`get` but aborts with 404 if not found instead of returning ``None``."""

        rv = self.get(ident)
        if rv is None:
            # abort(format_error_response(EntityNotFound(self.column_descriptions[0]['name'], ident)))
            raise EntityNotFound(self.column_descriptions[0]['name'], ident)
        return rv

    def first_or_raise(self, description=None):
        """Like :meth:`first` but aborts with 404 if not found instead of returning ``None``."""

        rv = self.first()
        if rv is None:
            # abort(format_error_response(NoDataFound(self.column_descriptions[0]['name'])))
            raise NoDataFound(self.column_descriptions[0]['name'])
        return rv


class QueryWithSoftDelete(BaseQueryJSON):
    _with_deleted = False

    def __new__(cls, *args, **kwargs):
        obj = super(QueryWithSoftDelete, cls).__new__(cls)
        obj._with_deleted = kwargs.pop('_with_deleted', False)
        if len(args) > 0:
            super(QueryWithSoftDelete, obj).__init__(*args, **kwargs)
            return obj.filter_by(deleted=False) if not obj._with_deleted else obj
        return obj

    def __init__(self, *args, **kwargs):
        pass

    def with_deleted(self):
        from dimensigon.web import db
        return self.__class__(db.class_mapper(self._mapper_zero().class_),
                              session=db.session(), _with_deleted=True)

    def _get(self, *args, **kwargs):
        # this calls the original query.get function from the base class
        return super(QueryWithSoftDelete, self).get(*args, **kwargs)

    def get(self, *args, **kwargs):
        # the query.get method does not like it if there is a filter clause
        # pre-loaded, so we need to implement it using a workaround
        obj = self.with_deleted()._get(*args, **kwargs)
        return obj if obj is None or self._with_deleted or not obj.deleted else None


def filter_query(entity, req_args: dict, exclude: t.Container = None):
    """Generates a sqlalchemy query object filtered by filters.

    entity: entity to filter
    filters: filters in JSON API format https://jsonapi.org/format/#fetching-filtering
    exclude: columns to exclude on filter

    """
    filters = []
    for k, v in req_args.items():
        if k.startswith('filter['):
            m = re.search('^filter\[(\w+)\]$', k)
            if m:
                filters.append((m.group(1), v))
    query = entity.query
    for k, v in filters:
        column = getattr(entity, k, None)
        if not column or k in (exclude or []):
            return {'error': f'Invalid filter column: {k}'}, 404
        if ',' in v:
            values = v.split(',')
            query = query.filter(column.in_(values))
        else:
            if v.lower() == 'true':
                v = True
            elif v.lower() == 'false':
                v = False
            query = query.filter(column == v)
    return query


def check_param_in_uri(param):
    return param in request.args.getlist('params')


def run_in_background(func: t.Callable, app=None, args=None, kwargs=None):
    args = args or ()
    kwargs = kwargs or {}
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        app = app

    def thread_with_app_context():
        with app.app_context():
            run(func(*args, **kwargs))

    th = threading.Thread(target=thread_with_app_context)
    # th.daemon = True
    th.start()


class DatetimeEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, dt.datetime):
            return obj.strftime(defaults.DATETIME_FORMAT)
        return JSONEncoder.default(self, obj)


def json_format_error():
    return {'error': format_error()}


def format_error():
    exc_type, exc_value, exc_traceback = sys.exc_info()
    return traceback.format_exc() if current_app.config['DEBUG'] else str(exc_value)


def search(server_or_granule, servers: t.List['Server'], ids: bool = False) -> t.Union[t.List['Server'], t.List[Id]]:
    """
    Searches the server from list of servers
    Args:
        server_or_granule: server id, name or granule to search
        servers: list of servers
        ids: determines if it should return a list of ids or Servers

    Returns:

    """
    if server_or_granule == 'all':
        return servers
    server_list = [(str(server.id) if ids else server) for server in servers if server.id == server_or_granule]
    if not server_list:
        server_list = [(str(server.id) if ids else server) for server in servers if server_or_granule == server.name]
        if not server_list:
            server_list = [(str(server.id) if ids else server) for server in servers if
                           server_or_granule in server.granules]
    return server_list


def normalize_hosts(hosts: t.Dict[str, t.Union[str, t.List[str]]]) -> t.List[str]:
    """ normalizes all str to server ids

    Args:
        hosts: data structure containing name, granules or id to convert into

    Returns:
        list: servers not found in catalog

    Examples:
        >>> normalize_hosts({'front': 'node1', 'back': 'tibero', 'all': ['node1', 'tibero', 'id_node4']})
        { 'all': ['id_node1', 'id_tibero_node2', 'id_tibero_node3', 'id_node4'],
          'databases': ['id_tibero_node2', 'id_tibero_node3'],
          'front': ['id_node1']}

    """
    from dimensigon.domain.entities import Server

    not_found = []
    servers = Server.query.all()
    for target, v in hosts.items():
        server_list = []
        if is_iterable_not_string(v):
            for vv in v:
                sl = search(vv, servers, ids=True)
                if len(sl) == 0:
                    not_found.append(vv)
                else:
                    server_list.extend(sl)
        else:
            sl = search(v, servers, ids=True)
            if len(sl) == 0:
                not_found.append(v)
            else:
                server_list.extend(sl)
        hosts[target] = server_list
    return not_found


@contextmanager
def session_scope():
    from dimensigon.web import db
    engine = db.get_engine()
    Session = sessionmaker(bind=engine)
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


def get_auth_from_request():
    return HTTPBearerAuth(request.headers['Authorization'].split()[1])


def generate_http_auth(identity=None, **kwargs) -> HTTPBearerAuth:
    identity = identity or get_jwt_identity()
    if not kwargs:
        kwargs['minutes'] = 15
    return HTTPBearerAuth(create_access_token(identity=identity, expires_delta=dt.timedelta(**kwargs)))


def get_root_auth(**kwargs):
    return generate_http_auth(identity='00000000-0000-0000-0000-000000000001', **kwargs)


@contextmanager
def transaction(session=None):
    from dimensigon.web import db
    if not session:
        session = db.session
    try:
        yield
        session.commit()
    except Exception:
        session.rollback()
        raise


def get_servers_from_scope(scope: 'Scope', bypass: t.Union[t.List['Server'], 'Server'] = None) -> t.List['Server']:
    """
    Returns the servers to lock for the related scope

    Parameters
    ----------
    scope: Scope

    Returns
    -------

    """
    from dimensigon.domain.entities import Server

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
