"""Flask blueprint for Stripe billing endpoints (Phase 2).

ENV-GATED behaviour
-------------------
The blueprint always registers (registration must never raise), but every
route is guarded by :func:`_require_service`. When ``STRIPE_API_KEY`` is unset
:meth:`StripeService.from_app` returns ``None`` and the route responds with a
clean HTTP 503 "billing not configured" — it never crashes and never touches
the Stripe SDK.

Routes
------
* ``POST /api/billing/checkout``         — create a Checkout session.
* ``POST /api/billing/webhooks/stripe``  — Stripe webhook sink. Verifies the
  ``Stripe-Signature`` header (HTTP 400 on failure) and applies events
  idempotently.

These endpoints are deliberately plain Flask views. The webhook is invoked by
Stripe (an external caller), so the mesh-internal ``@securizer`` /
``@forward_or_dispatch`` decorators do NOT apply and are intentionally omitted.
"""
import logging

from flask import Blueprint, current_app, request

from .service import (
    BillingNotConfigured,
    InvalidWebhookSignature,
    StripeService,
)

_LOGGER = logging.getLogger('dm.billing')

blueprint_name = 'billing'
billing_bp = Blueprint(blueprint_name, __name__, url_prefix='/api/billing')


def _require_service():
    """Return (service, None) or (None, (body, status)) when unconfigured."""
    service = StripeService.from_app(current_app)
    if service is None:
        return None, (
            {
                'error': 'billing_not_configured',
                'message': 'Billing is not configured on this node. '
                           'Set STRIPE_API_KEY to enable billing.',
            },
            503,
        )
    return service, None


@billing_bp.route('/checkout', methods=['POST'])
def create_checkout():
    """Create a Stripe Checkout session for a tier upgrade.

    Body (JSON): ``{"tier": "pro"|"enterprise"|"community", "owner_email": "...",
    "node_count": <int>}``. Returns the Checkout session id/url, or — for the
    free community tier — the minted licence.
    """
    service, unconfigured = _require_service()
    if unconfigured is not None:
        return unconfigured

    data = request.get_json(silent=True) or {}
    tier = data.get('tier')
    owner_email = data.get('owner_email')
    node_count = data.get('node_count', 1)

    if not tier:
        return {'error': 'bad_request', 'message': "'tier' is required"}, 400
    if not owner_email:
        return {'error': 'bad_request', 'message': "'owner_email' is required"}, 400

    try:
        result = service.create_checkout_session(
            tier=tier, owner_email=owner_email, node_count=node_count
        )
    except ValueError as e:
        return {'error': 'bad_request', 'message': str(e)}, 400
    except BillingNotConfigured as e:
        # e.g. requested a paid tier whose STRIPE_PRICE_* is unset.
        return {'error': 'billing_not_configured', 'message': str(e)}, 503
    except Exception:  # pragma: no cover - upstream Stripe/API failure
        _LOGGER.exception("Failed to create checkout session")
        return {'error': 'checkout_failed',
                'message': 'Unable to create checkout session'}, 502

    return result, 200


@billing_bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Stripe webhook sink.

    Verifies the ``Stripe-Signature`` header against ``STRIPE_WEBHOOK_SECRET``
    BEFORE acting (HTTP 400 on failure), then applies the event idempotently.
    """
    service, unconfigured = _require_service()
    if unconfigured is not None:
        return unconfigured

    # IMPORTANT: signature verification needs the EXACT raw bytes, not a parsed
    # body. Do not use request.get_json() here.
    payload = request.get_data()
    signature_header = request.headers.get('Stripe-Signature')

    try:
        event = service.verify_event(payload, signature_header)
    except InvalidWebhookSignature as e:
        # Reject invalid/missing signatures with 400 (per the safety contract).
        _LOGGER.warning("Rejected Stripe webhook: %s", e)
        return {'error': 'invalid_signature', 'message': str(e)}, 400
    except BillingNotConfigured as e:
        # Webhook secret missing — cannot verify, so we refuse rather than trust.
        return {'error': 'billing_not_configured', 'message': str(e)}, 503

    try:
        result = service.handle_event(event)
    except Exception:  # pragma: no cover - defensive
        _LOGGER.exception("Failed to handle verified Stripe event")
        # Returning 500 lets Stripe retry; idempotency makes retries safe.
        return {'error': 'handler_failed'}, 500

    return result, 200
