"""Helpers for tool identity from injected agent state."""

from uuid import UUID


def get_user_id(state: dict[str, object] | None) -> str:
    if not state:
        raise ValueError("Missing injected state")
    user_id = state.get("user_id")
    if not user_id:
        raise ValueError("Missing user_id in injected state")
    return str(user_id)


def get_user_uuid(state: dict[str, object] | None) -> UUID:
    return UUID(get_user_id(state))
