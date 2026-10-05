from pytest import MonkeyPatch

from gordie.integrations.defaults import default_plugins
from gordie.plugins import UnrestrictedAccess


def test_default_plugins_without_creem_credentials_have_no_payment_surface(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("CREEM_API_KEY", raising=False)
    plugins = default_plugins()
    assert isinstance(plugins.access, UnrestrictedAccess)
    assert plugins.tools == plugins.routes == ()
    plugins.storage.close()
