import logging

from flask import current_app

from dimensigon.domain.entities import Server
from dimensigon.use_cases import routing
from dimensigon.utils import asyncio
from dimensigon.web import network as ntwrk

logger = logging.getLogger('dimensigon.cluster')


async def send_cluster_register(cr, servers=None, auth=None, exclude=None):
    if not servers:
        servers = Server.get_neighbours(exclude=exclude)
    responses = await ntwrk.parallel_requests(servers, 'post',
                                              view_or_url='api_1_0.cluster',
                                              json=cr,
                                              auth=auth,
                                              timeout=10)

    for r, s in zip(responses, servers):
        if not r.ok and logger.level <= logging.WARNING:
            logger.warning(
                f"Unable to send cluster information to {s}. Response: {r}")


def check_server_alive(server: Server):
    alive_server_ids = [i for i in current_app.cluster if server.id != i and i != Server.get_current().id]
    # check if I have it as a neighbour
    if server.route.cost == 0:
        route = routing.check_gates(server)
        if route:
            return True

    # in order to prevent broadcast to everyone, first try a ping
    cost, elapsed = ntwrk.ping(server, Server.get_current(), retries=1, timeout=15)
    if cost is not None:
        return True
    responses = asyncio.run(ntwrk.parallel_requests(alive_server_ids, 'get',
                                                    view_or_url='api_1_0.routes_neighbour',
                                                    view_data=dict(server_id=server.id), timeout=10))
    for r in responses:
        if r.ok:
            if r.msg.get('neighbour'):
                return True
    return False


def update_cluster_status():
    alive_server_ids = current_app.cluster.get_alive()
    updated = False
    for alive_server_id in alive_server_ids:
        if alive_server_id != Server.get_current().id:
            alive = check_server_alive(Server.query.get(Server))
            if not alive:
                current_app.cluster.set_death(alive_server_id)
                updated = True
    return updated