"""Use cases for multi-dimension federation peering management."""
import logging
import uuid

from sqlalchemy import select

from dimensigon.web import db

logger = logging.getLogger('dm.federation')


def initiate_peering(endpoint, name):
    """Create a new Peer in 'pending' status and return its id."""
    from dimensigon.domain.entities.federation import Peer

    peer = Peer(
        id=str(uuid.uuid4()),
        name=name,
        endpoint=endpoint,
        status='pending',
    )
    db.session.add(peer)
    db.session.commit()
    logger.info('Initiated peering with %s at %s (id=%s)', name, endpoint, peer.id)
    return peer.id


def accept_peering(peer_id):
    """Set peer status to 'connected'."""
    from dimensigon.domain.entities.federation import Peer

    peer = db.session.get(Peer, peer_id)
    if not peer:
        return None
    peer.status = 'connected'
    db.session.commit()
    logger.info('Accepted peering for peer %s (%s)', peer.name, peer_id)
    return peer


def revoke_peering(peer_id):
    """Set peer status to 'revoked' and deactivate all its federation links."""
    from dimensigon.domain.entities.federation import Peer, FederationLink

    peer = db.session.get(Peer, peer_id)
    if not peer:
        return None
    peer.status = 'revoked'

    links = db.session.execute(
        select(FederationLink).where(FederationLink.peer_id == peer_id)
    ).scalars().all()
    for link in links:
        link.active = False

    db.session.commit()
    logger.info('Revoked peering for peer %s (%s)', peer.name, peer_id)
    return peer


def get_peer_status(peer_id):
    """Return peer info together with its federation links."""
    from dimensigon.domain.entities.federation import Peer

    peer = db.session.get(Peer, peer_id)
    if not peer:
        return None
    data = peer.to_json()
    data['links'] = [link.to_json() for link in peer.links.all()]
    return data


def list_peers():
    """Return all peers with their current status."""
    from dimensigon.domain.entities.federation import Peer

    peers = db.session.execute(select(Peer)).scalars().all()
    return [p.to_json() for p in peers]
