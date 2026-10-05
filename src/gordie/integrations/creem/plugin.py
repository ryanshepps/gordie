from dataclasses import replace

from gordie.integrations.creem import validate_billing_config
from gordie.integrations.creem.tier import (
    _email_for_user_id,
    build_upgrade_message_by_user_id,
    check_league_limit_by_user_id,
    check_question_allowed,
)
from gordie.plugins import AccessDecision, AccessRequest, Action, Plugins


class CreemAccessPolicy:
    def evaluate(self, request: AccessRequest) -> AccessDecision:
        if request.action is Action.CONNECT_TEAM:
            allowed, reason = check_league_limit_by_user_id(request.user_id)
        else:
            email = _email_for_user_id(request.user_id)
            if email is None:
                return AccessDecision(False, "Connect an email identity before managing your plan.")
            allowed, reason = check_question_allowed(email, request.message)
        if allowed:
            return AccessDecision(True)
        return AccessDecision(
            False, build_upgrade_message_by_user_id(request.user_id, reason, "email")
        )


def with_creem(plugins: Plugins) -> Plugins:
    from gordie.integrations.creem.tools.generate_checkout_link import generate_checkout_link
    from gordie.integrations.creem.tools.generate_portal_link import generate_portal_link
    from gordie.integrations.creem.tools.get_subscription_status import get_subscription_status

    validate_billing_config()
    return replace(
        plugins,
        access=CreemAccessPolicy(),
        extra_tools=(
            *plugins.extra_tools,
            get_subscription_status,
            generate_checkout_link,
            generate_portal_link,
        ),
    )
