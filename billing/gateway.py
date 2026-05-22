"""BillingGateway protocol and implementations."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class BillingGateway(Protocol):
    def check_question_allowed(self, email: str, message: str) -> tuple[bool, str]: ...
    def check_usage_allowed(self, email: str, action: str) -> tuple[bool, str]: ...
    def check_league_limit(self, email: str) -> tuple[bool, str]: ...
    def get_user_tier(self, email: str) -> str: ...
    def build_billing_context(self, email: str, reason: str, channel: str) -> str: ...
    def build_upgrade_message(self, email: str, reason: str, channel: str) -> str: ...


class NullBillingGateway:
    """No-op gateway for self-hosted deployments without Creem keys.

    All permission checks pass. Billing context is never injected.
    """

    def check_question_allowed(self, email: str, message: str) -> tuple[bool, str]:
        return (True, "")

    def check_usage_allowed(self, email: str, action: str) -> tuple[bool, str]:
        return (True, "")

    def check_league_limit(self, email: str) -> tuple[bool, str]:
        return (True, "")

    def get_user_tier(self, email: str) -> str:
        return "free"

    def build_billing_context(self, email: str, reason: str, channel: str) -> str:
        return ""

    def build_upgrade_message(self, email: str, reason: str, channel: str) -> str:
        return reason


class CreemBillingGateway:
    """Production gateway backed by Creem and tier enforcement."""

    def check_question_allowed(self, email: str, message: str) -> tuple[bool, str]:
        from billing.tier import check_question_allowed

        return check_question_allowed(email, message)

    def check_usage_allowed(self, email: str, action: str) -> tuple[bool, str]:
        from billing.tier import check_usage_allowed

        return check_usage_allowed(email, action)

    def check_league_limit(self, email: str) -> tuple[bool, str]:
        from billing.tier import check_league_limit

        return check_league_limit(email)

    def get_user_tier(self, email: str) -> str:
        from billing.tier import get_user_tier

        return get_user_tier(email)

    def build_billing_context(self, email: str, reason: str, channel: str) -> str:
        from billing.tier import build_billing_context

        return build_billing_context(email, reason, channel)

    def build_upgrade_message(self, email: str, reason: str, channel: str) -> str:
        from billing.tier import build_upgrade_message

        return build_upgrade_message(email, reason, channel)
