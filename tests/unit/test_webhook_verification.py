"""Tests for webhook verification helpers."""

from nacl.signing import SigningKey

from server.webhook_verification import verify_discord_interaction


def test_verify_discord_interaction_accepts_valid_signature(monkeypatch) -> None:
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", verify_key.encode().hex())
    monkeypatch.setattr("server.webhook_verification.time.time", lambda: 1700000100)

    timestamp = "1700000000"
    body = b'{"type":1}'
    signature = signing_key.sign(timestamp.encode("utf-8") + body).signature.hex()

    assert verify_discord_interaction(signature, timestamp, body) is True


def test_verify_discord_interaction_rejects_invalid_signature(monkeypatch) -> None:
    signing_key = SigningKey.generate()
    other_key = SigningKey.generate()
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", signing_key.verify_key.encode().hex())
    monkeypatch.setattr("server.webhook_verification.time.time", lambda: 1700000100)

    timestamp = "1700000000"
    body = b'{"type":1}'
    signature = other_key.sign(timestamp.encode("utf-8") + body).signature.hex()

    assert verify_discord_interaction(signature, timestamp, body) is False


def test_verify_discord_interaction_rejects_stale_timestamp(monkeypatch) -> None:
    signing_key = SigningKey.generate()
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", signing_key.verify_key.encode().hex())
    monkeypatch.setattr("server.webhook_verification.time.time", lambda: 1700000600)

    timestamp = "1700000000"
    body = b'{"type":1}'
    signature = signing_key.sign(timestamp.encode("utf-8") + body).signature.hex()

    assert verify_discord_interaction(signature, timestamp, body) is False


def test_verify_discord_interaction_rejects_invalid_timestamp(monkeypatch) -> None:
    signing_key = SigningKey.generate()
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", signing_key.verify_key.encode().hex())

    body = b'{"type":1}'
    signature = signing_key.sign(b"not-a-timestamp" + body).signature.hex()

    assert verify_discord_interaction(signature, "not-a-timestamp", body) is False


def test_verify_discord_interaction_rejects_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("DISCORD_PUBLIC_KEY", raising=False)

    assert verify_discord_interaction("bad", "1700000000", b"{}") is False
