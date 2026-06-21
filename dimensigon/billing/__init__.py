"""Billing package (Phase 2 — Stripe-backed licensing).

ADDITIVE + ENV-GATED. Nothing in this package touches the network or the
Stripe SDK at import time. The Stripe client is only ever configured lazily,
inside :class:`StripeService`, when an actual billing request arrives AND
``STRIPE_API_KEY`` is set. Importing this package (and registering its
blueprint) must therefore NEVER raise when the Stripe env vars are absent.

Public surface:
    - ``License`` / ``LicenseTier`` / ``LicenseStatus`` — SQLAlchemy model + enums.
    - ``ProcessedStripeEvent`` — idempotency ledger for webhook event ids.
    - ``StripeService`` — checkout session creation + webhook handling.
    - ``billing_bp`` — Flask blueprint with the two billing routes.
    - ``BillingNotConfigured`` — raised when Stripe is unconfigured.
"""

# Models are imported eagerly so they register with db.Model.metadata when this
# package is imported by the entities catalog. These imports are pure SQLAlchemy
# declarations and do NOT import the `stripe` SDK.
from .models import (  # noqa: F401
    License,
    LicenseTier,
    LicenseStatus,
    ProcessedStripeEvent,
)

# The service and blueprint are intentionally NOT imported here to keep this
# module free of any `stripe`/Flask-request dependency at catalog-import time.
# Import them from their submodules:
#     from dimensigon.billing.service import StripeService, BillingNotConfigured
#     from dimensigon.billing.routes import billing_bp

__all__ = [
    "License",
    "LicenseTier",
    "LicenseStatus",
    "ProcessedStripeEvent",
]
