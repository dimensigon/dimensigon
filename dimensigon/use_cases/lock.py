import logging
import time
import typing as t
from contextlib import contextmanager
from uuid import UUID

from flask_jwt_extended import create_access_token, get_jwt_identity
from sqlalchemy.orm import sessionmaker


from dimensigon import defaults
from dimensigon.domain.entities import Server, Catalog
from dimensigon.domain.entities.locker import Scope
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web.helpers import get_servers_from_scope
from dimensigon.utils.asyncio import run, create_task
from dimensigon.utils.helpers import is_iterable_not_string
from dimensigon.utils.typos import Id
from dimensigon.web import errors, db
from dimensigon.web.network import async_post, Response

logger = logging.getLogger('dm.lock')


async def request_locker(servers: t.Union[Server, t.List[Server]], action, scope, applicant, auth=None,
                         datemark=None) -> t.List[Response]:
    tasks = []
    server_responses = []
    if is_iterable_not_string(servers):
        it = servers
    else:
        it = [servers]
    payload = dict(scope=scope.name, applicant=applicant)
    if datemark:
        payload.update(datemark=datemark)

    for server in it:
        tasks.append(create_task(async_post(server, 'api_1_0.locker_' + action,
                                            json=payload,
                                            auth=auth,
                                            timeout=defaults.TIMEOUT_LOCK_REQUEST)))
    for server in it:
        r = await tasks.pop(0)
        server_responses.append(r)

    return server_responses


def lock_unlock(action: str, scope: Scope, servers: t.List[Server], applicant=None):
    """

    Parameters
    ----------
    action
        'U' for unlocking and 'L' for locking
    scope
        scope of the lock
    servers
        servers to ask for a lock

    Raises
    ------
    Raises an error if something went wrong

    Returns
    -------
    None
        returns none if all went as expected.
    """

    assert action in 'UL'

    applicant = applicant or [str(s.id) for s in servers]

    token = create_access_token(get_jwt_identity())
    auth = HTTPBearerAuth(token)
    if action == 'U':
        pool_responses = run(
            request_locker(servers=servers, scope=scope, action='unlock', applicant=applicant, auth=auth))

        if len(servers) == len([r for r in pool_responses if r.code in (200, 210)]):
            return
    else:
        action = 'P'
        catalog_ver = Catalog.max_catalog(str)
        pool_responses = run(
            request_locker(servers=servers, scope=scope, action='prevent', applicant=applicant, datemark=catalog_ver,
                           auth=auth))

        if len(servers) == len([r for r in pool_responses if r.code in (200, 210)]):
            action = 'L'
            pool_responses = run(
                request_locker(servers=servers, scope=scope, action='lock', applicant=applicant, auth=auth))
            if len(servers) == len([r for r in pool_responses if r.code in (200, 210)]):
                return

    raise errors.LockError(scope, action, [r for r in pool_responses if r.code not in (200, 210)])


def lock(scope: Scope, servers: t.List[Server] = None, applicant=None, retries=0, delay=3) -> UUID:
    """
    locks the Locker if allowed
    Parameters
    ----------
    scope
        scope that lock will affect.
    servers
        if scope set to Scope.ORCHESTRATION,
    applicant
        identifier of the lock
    Returns
    -------
    Result
    """

    if servers is not None:
        servers = servers if is_iterable_not_string(servers) else [servers]
        if len(servers) == 0:
            servers = None

    servers = servers or get_servers_from_scope(scope)

    if len(servers) == 0:
        raise errors.NoServerToLock(scope)

    applicant = applicant if applicant is not None else [str(s.id) for s in servers]

    _try = 1
    while True:
        try:
            lock_unlock(action='L', scope=scope, servers=servers, applicant=applicant)
        except errors.LockError as e:
            if _try < retries:
                _try += 1
                logger.info(f"Retrying to lock on {scope.name} in {delay} seconds")
                time.sleep(delay)
            else:
                error_servers = [r.server for r in e.responses]
                locked_servers = list(set(server for server in servers) - set(error_servers))
                lock_unlock('U', scope, servers=locked_servers, applicant=applicant)
                raise e
        else:
            break

    return applicant


def unlock(scope: Scope, applicant, servers: t.Union[t.List[Server], t.List[Id]] = None):
    """
    unlocks the Locker if allowed
    Parameters
    ----------
    scope

    Returns
    -------

    """
    if scope.ORCHESTRATION == scope and servers is None:
        raise ValueError('servers must be set')

    s = None
    if servers:
        if not isinstance(servers[0], Server):
            engine = db.get_engine()
            Session = sessionmaker(bind=engine)
            s = Session()
            servers = [s.session.query(Server).get(s) for s in servers]
    servers = servers or get_servers_from_scope(scope)

    if not servers:
        if s:
            s.close()
        raise RuntimeError('no server to unlock')

    try:
        lock_unlock(action='U', scope=scope, servers=servers, applicant=applicant)
    except errors.LockError as e:
        logger.warning(f"Unable to unlock: {e}")
    if s:
        s.close()


@contextmanager
def lock_scope(scope: Scope, servers: t.Union[t.List[Server], Server] = None,
               bypass: t.Union[t.List[Server], Server] = None, retries=0, delay=3, applicant=None):
    if servers is not None:
        servers = servers if is_iterable_not_string(servers) else [servers]
        if len(servers) == 0:
            servers = None

    servers = servers or get_servers_from_scope(scope, bypass)

    logger.debug(f"Requesting Lock on {scope.name} to the following servers: {[s.name for s in servers]}")
    _try = 1

    applicant = lock(scope, servers=servers, applicant=applicant, retries=retries, delay=delay)
    try:
        yield applicant
    finally:
        unlock(scope, servers=servers, applicant=applicant)
