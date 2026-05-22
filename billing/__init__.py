"""Billing package — all Creem/subscription functionality lives here.

Gated by CREEM_API_KEY presence. When absent, billing is disabled and
NullBillingGateway is returned, which allows all operations and exposes
no billing surface.
"""

import os

from billing.errors import BillingError
from billing.gateway import BillingGateway, CreemBillingGateway, NullBillingGateway
from billing.jobs import expire_trials_and_notify
from billing.webhook import register_routes

_CREEM_API_KEY: str = os.getenv("CREEM_API_KEY", "")
_CREEM_WEBHOOK_SECRET: str = os.getenv("CREEM_WEBHOOK_SECRET", "")

billing_enabled: bool = bool(_CREEM_API_KEY)

__all__ = [
    "BillingError",
    "billing_enabled",
    "expire_trials_and_notify",
    "get_gateway",
    "register_routes",
    "validate_billing_config",
]


def validate_billing_config() -> None:
    """Raise RuntimeError at startup if Creem config is partially set."""
    if _CREEM_API_KEY and not _CREEM_WEBHOOK_SECRET:
        raise RuntimeError(
            "CREEM_API_KEY is set but CREEM_WEBHOOK_SECRET is missing. "
            "Both are required when billing is enabled. "
            "Set CREEM_WEBHOOK_SECRET or unset CREEM_API_KEY to disable billing."
        )


def get_gateway() -> BillingGateway:
    """Return the active billing gateway.

    Returns CreemBillingGateway when billing is enabled, NullBillingGateway
    otherwise. NullBillingGateway allows all operations without Creem keys.
    """
    if billing_enabled:
        return CreemBillingGateway()
    return NullBillingGateway()
