"""Peer and FederationLink models for multi-dimension federation."""
import uuid

from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.utils.helpers import get_now
from dimensigon.web import db


class Peer(db.Model):
    __tablename__ = 'L_peer'

    id = db.Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(256), nullable=False)
    dimension_id = db.Column(UUID, nullable=True)
    endpoint = db.Column(db.String(2048), nullable=False)
    public_key = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(64), default='pending')  # pending, connected, disconnected, revoked
    last_seen = db.Column(UtcDateTime, nullable=True)
    created_at = db.Column(UtcDateTime, default=get_now)

    links = db.relationship('FederationLink', backref='peer', lazy='dynamic',
                            cascade='all, delete-orphan')

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'dimension_id': self.dimension_id,
            'endpoint': self.endpoint,
            'public_key': self.public_key,
            'status': self.status,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class FederationLink(db.Model):
    __tablename__ = 'L_federation_link'

    id = db.Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    peer_id = db.Column(UUID, db.ForeignKey('L_peer.id'), nullable=False)
    link_type = db.Column(db.String(64), nullable=False)  # execution, templates, routing
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(UtcDateTime, default=get_now)

    def to_json(self):
        return {
            'id': self.id,
            'peer_id': self.peer_id,
            'link_type': self.link_type,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
