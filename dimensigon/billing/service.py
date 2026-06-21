"""Stripe integration service for Phase 2 licensing.

SAFETY CONTRACT
---------------
* The ``stripe`` SDK is imported **lazily**, inside methods — importing this
  module never requires ``stripe`` to be installed and never touches the
  network. If ``STRIPE_API_KEY`` is unset, :func:`from_app` returns ``None``
  and the routes turn that into a clean HTTP 503.
* Webhook signature verification via ``stripe.Webhook.construct_event`` against
  ``STRIPE_WEBHOOK_SECRET`` is **mandatory** and happens BEFORE any state
  change. An invalid/missing signature raises :class:`InvalidWebhookSignature`,
  which the route maps to HTTP 400.
* Webhook handling is **idempotent**: each Stripe ``event.id`` is recorded in
  ``ProcessedStripeEvent``; a replayed id is a no-op.
"""
import logging
import secrets
import typing as t

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from dimensigon.utils.helpers import get_now
from dimensigon.web import db
from .models import (
    License,
    LicenseStatus,
    LicenseTier,
    ProcessedStripeEvent,
)

_LOGGER = logging.getLogger('dm.billing')

# Map our tier name -> the config key that holds the Stripe Price ID. Price IDs
# are ALWAYS read from config/env (never hardcoded). 'community' is free and has
# no Stripe price.
_TIER_PRICE_CONFIG_KEY = {
    LicenseTier.pro: 'STRIPE_PRICE_PRO',
    LicenseTier.enterprise: 'STRIPE_PRICE_ENTERPRISE',
}


class BillingNotConfigured(Exception):
    """Raised when a billing operation is attempted but Stripe is unconfigured."""


class InvalidWebhookSignature(Exception):
    """Raised when the Stripe-Signature header fails verification."""


class StripeService:
    """Thin wrapper around the Stripe SDK.

    Instantiate via :meth:`from_app` so construction is centrally gated on
    ``STRIPE_API_KEY`` being present. Direct construction is allowed (e.g. for
    tests) but still only configures the lazily-imported SDK.
    """

    def __init__(self, api_key: str, webhook_secret: t.Optional[str] = None,
                 price_ids: t.Optional[t.Mapping[str, t.Optional[str]]] = None,
                 success_url: t.Optional[str] = None,
                 cancel_url: t.Optional[str] = None):
        self._api_key = api_key
        self._webhook_secret = webhook_secret
        self._price_ids = dict(price_ids or {})
        self._success_url = success_url
        self._cancel_url = cancel_url

    # -- construction -------------------------------------------------------
    @classmethod
    def from_app(cls, app) -> t.Optional['StripeService']:
        """Build a service from app config, or ``None`` if Stripe is unconfigured.

        Returning ``None`` (rather than raising) is what lets the routes answer
        503 without the import/registration path ever touching Stripe.
        """
        api_key = app.config.get('STRIPE_API_KEY')
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            webhook_secret=app.config.get('STRIPE_WEBHOOK_SECRET'),
            price_ids={
                LicenseTier.community.value: app.config.get('STRIPE_PRICE_COMMUNITY'),
                LicenseTier.pro.value: app.config.get('STRIPE_PRICE_PRO'),
                LicenseTier.enterprise.value: app.config.get('STRIPE_PRICE_ENTERPRISE'),
            },
            success_url=app.config.get('STRIPE_CHECKOUT_SUCCESS_URL'),
            cancel_url=app.config.get('STRIPE_CHECKOUT_CANCEL_URL'),
        )

    def _stripe(self):
        """Lazily import + configure the Stripe SDK.

        Import is deferred so the absence of the ``stripe`` package never breaks
        app import/startup. Only called from request-handling code paths that
        already require a configured key.
        """
        try:
            import stripe
        except ImportError as e:  # pragma: no cover - depends on env
            raise BillingNotConfigured(
                "The 'stripe' package is not installed; cannot process billing."
            ) from e
        stripe.api_key = self._api_key
        return stripe

    # -- checkout -----------------------------------------------------------
    @staticmethod
    def generate_license_key() -> str:
        """Cryptographically-strong, URL-safe license key."""
        return 'DM-' + secrets.token_urlsafe(32)

    def price_id_for_tier(self, tier: LicenseTier) -> t.Optional[str]:
        key = _TIER_PRICE_CONFIG_KEY.get(tier)
        if key is None:
            return None
        return self._price_ids.get(tier.value)

    def create_checkout_session(self, tier: str, owner_email: str,
                                node_count: int = 1) -> dict:
        """Create a Stripe Checkout session for a paid tier upgrade.

        Reads the Stripe Price ID from config (``STRIPE_PRICE_*``). Raises
        :class:`BillingNotConfigured` if the requested tier has no configured
        price. 'community' is free and is handled by minting a licence directly
        rather than through Checkout.
        """
        try:
            tier_enum = LicenseTier(tier)
        except ValueError:
            raise ValueError(f"Unknown tier '{tier}'")

        if tier_enum is LicenseTier.community:
            # Free tier: no payment required, mint immediately.
            lic = self._mint_license(
                owner_email=owner_email,
                tier=tier_enum,
                node_count=node_count,
            )
            db.session.commit()
            return {'tier': 'community', 'license': lic.to_json()}

        price_id = self.price_id_for_tier(tier_enum)
        if not price_id:
            raise BillingNotConfigured(
                f"No Stripe price configured for tier '{tier}'. "
                f"Set {_TIER_PRICE_CONFIG_KEY[tier_enum]}."
            )

        stripe = self._stripe()
        session = stripe.checkout.Session.create(
            mode='subscription',
            line_items=[{'price': price_id, 'quantity': max(1, int(node_count))}],
            customer_email=owner_email,
            success_url=self._success_url or 'https://dimensigon.com/billing/success',
            cancel_url=self._cancel_url or 'https://dimensigon.com/billing/cancel',
            metadata={
                'tier': tier_enum.value,
                'owner_email': owner_email,
                'node_count': str(node_count),
            },
        )
        return {'id': session.id, 'url': session.url}

    # -- webhook ------------------------------------------------------------
    def verify_event(self, payload: bytes, signature_header: t.Optional[str]):
        """Verify the Stripe-Signature header and return the parsed event.

        MANDATORY signature check via ``stripe.Webhook.construct_event``.
        Raises :class:`InvalidWebhookSignature` on any failure (missing header,
        bad signature, malformed payload). The route maps that to HTTP 400.
        """
        if not self._webhook_secret:
            # Cannot verify without a secret — refuse rather than trust blindly.
            raise BillingNotConfigured(
                "STRIPE_WEBHOOK_SECRET is not set; cannot verify webhook."
            )
        if not signature_header:
            raise InvalidWebhookSignature("Missing Stripe-Signature header")

        stripe = self._stripe()
        try:
            event = stripe.Webhook.construct_event(
                payload, signature_header, self._webhook_secret
            )
        except ValueError as e:  # malformed payload
            raise InvalidWebhookSignature(f"Invalid payload: {e}") from e
        except stripe.error.SignatureVerificationError as e:
            raise InvalidWebhookSignature(f"Invalid signature: {e}") from e
        return event

    def handle_event(self, event) -> dict:
        """Idempotently apply a *verified* Stripe event.

        Must only be called with an event returned by :meth:`verify_event`.
        Duplicate event ids are no-ops (see ``ProcessedStripeEvent``).
        """
        event_id = event.get('id') if isinstance(event, dict) else getattr(event, 'id', None)
        event_type = event.get('type') if isinstance(event, dict) else getattr(event, 'type', None)

        if not event_id:
            # No id to dedupe on — treat as a no-op rather than risk a double mint.
            _LOGGER.warning("Stripe event with no id; ignoring (type=%s)", event_type)
            return {'status': 'ignored', 'reason': 'no event id'}

        # Idempotency gate: have we already processed this event?
        already = db.session.execute(
            select(ProcessedStripeEvent).filter_by(event_id=event_id)
        ).scalars().first()
        if already is not None:
            _LOGGER.info("Stripe event %s already processed; skipping", event_id)
            return {'status': 'duplicate', 'event_id': event_id}

        # Record the event first so concurrent duplicate deliveries collide on
        # the PK. The dispatch below runs in the same transaction.
        db.session.add(ProcessedStripeEvent(event_id=event_id, event_type=event_type))
        try:
            db.session.flush()
        except IntegrityError:
            # Lost a race with a concurrent delivery of the same event.
            db.session.rollback()
            _LOGGER.info("Stripe event %s raced; treated as duplicate", event_id)
            return {'status': 'duplicate', 'event_id': event_id}

        data_object = self._event_data_object(event)
        result = {'status': 'processed', 'event_id': event_id, 'type': event_type}

        if event_type == 'checkout.session.completed':
            lic = self._on_checkout_completed(data_object)
            result['license_key'] = lic.license_key if lic else None
        elif event_type == 'customer.subscription.deleted':
            revoked = self._on_subscription_deleted(data_object)
            result['revoked'] = revoked
        else:
            # Recorded for idempotency but no business action — that's fine.
            result['status'] = 'ignored'
            result['reason'] = f'unhandled event type {event_type}'

        db.session.commit()
        return result

    # -- internal event handlers -------------------------------------------
    @staticmethod
    def _event_data_object(event) -> dict:
        if isinstance(event, dict):
            return (event.get('data') or {}).get('object') or {}
        data = getattr(event, 'data', None)
        if data is None:
            return {}
        obj = getattr(data, 'object', None)
        if obj is None and isinstance(data, dict):
            obj = data.get('object')
        return obj or {}

    def _mint_license(self, owner_email: str, tier: LicenseTier,
                      node_count: int = 1,
                      stripe_customer_id: t.Optional[str] = None,
                      stripe_subscription_id: t.Optional[str] = None) -> License:
        lic = License(
            license_key=self.generate_license_key(),
            owner_email=owner_email,
            tier=tier,
            node_count=max(1, int(node_count or 1)),
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            status=LicenseStatus.active,
            issued_at=get_now(),
        )
        db.session.add(lic)
        return lic

    def _on_checkout_completed(self, obj: dict) -> t.Optional[License]:
        """Mint (or reactivate) a licence on a completed checkout session."""
        metadata = obj.get('metadata') or {}
        owner_email = (
            metadata.get('owner_email')
            or obj.get('customer_email')
            or (obj.get('customer_details') or {}).get('email')
        )
        tier_value = metadata.get('tier') or LicenseTier.pro.value
        try:
            tier = LicenseTier(tier_value)
        except ValueError:
            tier = LicenseTier.pro
        node_count = metadata.get('node_count')
        subscription_id = obj.get('subscription')
        customer_id = obj.get('customer')

        if not owner_email:
            _LOGGER.warning("checkout.session.completed without an email; cannot mint")
            return None

        # Idempotent against subscription id too: if a licence already exists for
        # this subscription, reactivate it instead of creating a duplicate.
        existing = None
        if subscription_id:
            existing = db.session.execute(
                select(License).filter_by(stripe_subscription_id=subscription_id)
            ).scalars().first()
        if existing is not None:
            existing.status = LicenseStatus.active
            existing.tier = tier
            existing.owner_email = owner_email
            if customer_id:
                existing.stripe_customer_id = customer_id
            _LOGGER.info("Reactivated existing license %s for subscription %s",
                         existing.license_key, subscription_id)
            return existing

        lic = self._mint_license(
            owner_email=owner_email,
            tier=tier,
            node_count=int(node_count) if node_count else 1,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
        )
        _LOGGER.info("Minted license %s (tier=%s) for %s",
                     lic.license_key, tier.value, owner_email)
        return lic

    def _on_subscription_deleted(self, obj: dict) -> int:
        """Revoke any licence tied to a cancelled subscription."""
        subscription_id = obj.get('id')
        if not subscription_id:
            return 0
        licenses = db.session.execute(
            select(License).filter_by(stripe_subscription_id=subscription_id)
        ).scalars().all()
        count = 0
        for lic in licenses:
            if lic.status != LicenseStatus.revoked:
                lic.status = LicenseStatus.revoked
                count += 1
                _LOGGER.info("Revoked license %s (subscription %s deleted)",
                             lic.license_key, subscription_id)
        return count
