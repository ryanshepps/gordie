from pytest import MonkeyPatch

from gordie import create_app
from gordie.integrations.defaults import default_plugins
from gordie.plugins import UnrestrictedAccess


async def test_default_plugins_have_no_payment_surface(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("CREEM_API_KEY", "unused")
    plugins = default_plugins()
    assert isinstance(plugins.access, UnrestrictedAccess)
    assert plugins.extra_tools == ()
    app = create_app(plugins, openrouter_api_key="test-key", model="openai/gpt-4o-mini")
    response = await app.test_client().post("/webhooks/creem", data=b"{}")
    assert response.status_code == 404
    app.runtime.close()
