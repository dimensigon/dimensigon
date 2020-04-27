import typing as t
from contextlib import contextmanager
from uuid import UUID

import aiohttp
from flask import current_app
from flask_jwt_extended import create_access_token, get_jwt_identity

import dm.use_cases.exceptions as ue
from dm.domain.entities import Server, Catalog
from dm.domain.entities.locker import Scope
from dm.use_cases.helpers import get_servers_from_scope
from dm.utils.asyncio import run
from dm.utils.helpers import is_iterable_not_string
from dm.web.network import async_post, HTTPBearerAuth


async def request_locker(servers: t.Union[Server, t.List[Server]], action, scope, applicant, auth=None,
                         datemark=None) -> \
        t.Dict[UUID, t.Tuple[t.Any, t.Optional[int]]]:
    server_responses = {}
    if is_iterable_not_string(servers):
        it = servers
    else:
        it = [servers]
    payload = dict(scope=scope.name, applicant=applicant)
    if datemark:
        payload.update(datemark=datemark)
    async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=current_app.config['SSL_VERIFY'])) as session:
        for server in it:
            server_responses[server.id] = await async_post(server, 'api_1_0.locker_' + action, session=session,
                                                           json=payload,
                                                           auth=auth)
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

        if len(servers) == len(list(filter(lambda r: r[1][1] == 200, [(k, v) for k, v in pool_responses.items()]))):
            return
    else:
        action = 'P'
        catalog_ver = Catalog.max_catalog(str)
        pool_responses = run(
            request_locker(servers=servers, scope=scope, action='prevent', applicant=applicant, datemark=catalog_ver, auth=auth))

        if len(servers) == len(list(filter(lambda r: r[1][1] == 200, [(k, v) for k, v in pool_responses.items()]))):
            action = 'L'
            pool_responses = run(
                request_locker(servers=servers, scope=scope, action='lock', applicant=applicant, auth=auth))
            if len(servers) == len(
                    list(filter(lambda r: r[1][1] == 200, [(k, v) for k, v in pool_responses.items()]))):
                return

    e = [ue.ErrorServerLock(server=Server.query.get(uid), msg=r[0], code=r[1]) for uid, r in pool_responses.items() if
         r[1] != 200]
    if action == 'L':
        raise ue.ErrorLock(scope=scope, errors=e)
    elif action == 'U':
        raise ue.ErrorUnLock(scope=scope, errors=e)
    else:
        raise ue.ErrorPreventingLock(scope=scope, errors=e)


def lock(scope: Scope, servers: t.List[Server] = None) -> UUID:
    """
    locks the Locker if allowed
    Parameters
    ----------
    scope
        scope that lock will affect.
    servers
        if scope set to Scope.ORCHESTRATION,
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
        raise RuntimeError('no server to lock')

    applicant = [str(s.id) for s in servers]
    try:
        lock_unlock(action='L', scope=scope, servers=servers, applicant=applicant)
    # exception goes here because we need the applicant to unlock already locked servers
    except (ue.ErrorLock, ue.ErrorPreventingLock) as e:
        error_servers = [es.server for es in e]
        locked_servers = list(set(server for server in servers) - set(error_servers))
        lock_unlock('U', scope, servers=locked_servers, applicant=applicant)
        raise
    return applicant


def unlock(scope: Scope, applicant, servers=None):
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

    servers = servers or get_servers_from_scope(scope)

    if not servers:
        raise RuntimeError('no server to unlock')

    lock_unlock(action='U', scope=scope, servers=servers, applicant=applicant)


@contextmanager
def lock_scope(scope: Scope, servers: t.Union[t.List[Server], Server] = None):
    if servers is not None:
        servers = servers if is_iterable_not_string(servers) else [servers]
        if len(servers) == 0:
            servers = None

    servers = servers or get_servers_from_scope(scope)

    applicant = lock(scope, servers)
    current_app.logger.debug(f"Lock on {scope.name} acquired on servers : {[s.name for s in servers]}")
    try:
        yield applicant
    finally:
        unlock(scope, servers=servers, applicant=applicant)
        current_app.logger.debug(f"Lock on {scope.name} released")
