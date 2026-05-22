"""Channel adapter registry construction."""

from server.adapters.base import AdapterRegistry, ChannelAdapter
from server.adapters.email_adapter import EmailAdapter
from server.adapters.sms_adapter import SmsAdapter


def build_registry() -> AdapterRegistry:
    adapters: tuple[ChannelAdapter, ...] = (EmailAdapter(), SmsAdapter())
    return AdapterRegistry({adapter.medium: adapter for adapter in adapters})
