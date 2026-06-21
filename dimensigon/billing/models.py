"""SQLAlchemy 2.x models for Stripe-backed licensing.

These are plain local (non-distributed) entities — they live only on the node
that runs the billing endpoint and are never gossiped through the catalog, so
they use ``db.Model`` directly (no ``DistributedEntityMixin``) with an ``L_``
table prefix, matching the convention used by ``Transfer`` (``L_transfer``).

Registered with ``db.Model.metadata`` simply by being imported (see
``dimensigon/billing/__init__.py`` and the import added to the entities
``__init__``), so ``db.Model.metadata.create_all`` picks them up exactly like
every other table.
"""
import uuid
from enum import Enum

from dimensigon.utils import typos
from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.utils.helpers import get_now
from dimensigon.web import db


class LicenseTier(Enum):
    community = 'community'
    pro = 'pro'
    enterprise = 'enterprise'


class LicenseStatus(Enum):
    active = 'active'
    expired = 'expired'
    revoked = 'revoked'


class License(db.Model):
    """A licence minted/revoked off the back of Stripe subscription events."""
    __tablename__ = 'L_license'

    id = db.Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    # The opaque key the customer installs on their mesh. Unique so a replayed
    # mint can't create two rows for the same key.
    license_key = db.Column(db.String(255), unique=True, nullable=False)
    owner_email = db.Column(db.String(255), nullable=False)
    tier = db.Column(typos.Enum(LicenseTier), nullable=False,
                     default=LicenseTier.community)
    node_count = db.Column(db.Integer, nullable=False, default=1)

    # Stripe linkage (nullable: a community licence has no Stripe footprint).
    stripe_customer_id = db.Column(db.String(255))
    stripe_subscription_id = db.Column(db.String(255))

    status = db.Column(typos.Enum(LicenseStatus), nullable=False,
                       default=LicenseStatus.active)
    issued_at = db.Column(UtcDateTime, nullable=False, default=get_now)
    expires_at = db.Column(UtcDateTime, nullable=True)

    def to_json(self):
        return {
            'id': str(self.id),
            'license_key': self.license_key,
            'owner_email': self.owner_email,
            'tier': self.tier.value if self.tier else None,
            'node_count': self.node_count,
            'stripe_customer_id': self.stripe_customer_id,
            'stripe_subscription_id': self.stripe_subscription_id,
            'status': self.status.value if self.status else None,
            'issued_at': self.issued_at.isoformat() if self.issued_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }

    def __repr__(self):
        return f'<License {self.license_key} tier={getattr(self.tier, "value", None)} status={getattr(self.status, "value", None)}>'


class ProcessedStripeEvent(db.Model):
    """Idempotency ledger for Stripe webhook delivery.

    Stripe may deliver the same event more than once (at-least-once delivery).
    We persist each handled ``event.id`` here; the webhook handler no-ops if the
    id is already present, so duplicate deliveries never mint/revoke twice.
    """
    __tablename__ = 'L_processed_stripe_event'

    # The Stripe event id (``evt_...``) IS the primary key — a duplicate insert
    # collides on the PK, which is exactly the idempotency guarantee we want.
    event_id = db.Column(db.String(255), primary_key=True)
    event_type = db.Column(db.String(255))
    processed_at = db.Column(UtcDateTime, nullable=False, default=get_now)

    def to_json(self):
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
        }

    def __repr__(self):
        return f'<ProcessedStripeEvent {self.event_id} {self.event_type}>'
