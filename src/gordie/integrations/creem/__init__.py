import os

_CREEM_API_KEY: str = os.getenv("CREEM_API_KEY", "")
_CREEM_WEBHOOK_SECRET: str = os.getenv("CREEM_WEBHOOK_SECRET", "")


def validate_billing_config() -> None:
    """Raise RuntimeError at startup if Creem config is partially set."""
    if _CREEM_API_KEY and not _CREEM_WEBHOOK_SECRET:
        raise RuntimeError(
            "CREEM_API_KEY is set but CREEM_WEBHOOK_SECRET is missing. "
            "Both are required when billing is enabled. "
            "Set CREEM_WEBHOOK_SECRET or unset CREEM_API_KEY to disable billing."
        )
