"""Maintenance-mode HTTP server.

Returns canned responses on every route so that no inbound request can reach
the agent, DB, or LLM keys. Run this in place of `server.server.Server` while
the project is being migrated to a hardened host.

Behaviour:
  /health            -> 200 OK (lets the Cloudflare tunnel + any external
                       healthcheck stay green)
  /api/signup        -> 503 with JSON { status: "open_source", message, ... }
                       so the public signup form can render a migration banner.
  /callback          -> 503 with a simple HTML page (anyone clicking a stale
                       OAuth link gets a clear explanation).
  /sms/webhook       -> 200 (silently consumed so Sinch does not retry-storm).
  /email/webhook     -> 200 (silently consumed so Mailgun does not retry-storm).
  Everything else    -> 503 with the open-source JSON payload.

This file imports nothing from `agent/`, `data/`, `scheduled/`, or `tools/`
on purpose. If you find yourself adding such an import here you have probably
defeated the point of running maintenance mode.
"""

import asyncio
import logging
import os

from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import Quart, jsonify

from module.logger import get_logger

GITHUB_URL = os.getenv("OSS_GITHUB_URL", "https://github.com/ryanshepps/gordie")

OSS_MESSAGE = (
    "Gordie has been open-sourced! The hosted instance is being migrated to a "
    "more secure environment. In the meantime, you can self-host from the "
    "GitHub repository."
)

logging.getLogger("hypercorn.access").setLevel(logging.ERROR)


def _oss_payload():
    return {
        "status": "open_source",
        "message": OSS_MESSAGE,
        "github_url": GITHUB_URL,
    }


def _oss_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Gordie — Open Source</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #05091D; color: #E8EDF5;
      min-height: 100vh; margin: 0;
      display: flex; align-items: center; justify-content: center;
      padding: 2rem;
    }}
    .card {{
      max-width: 520px; text-align: center;
      background: #0F1628; border: 1px solid #1E2D4A;
      border-radius: 0.5rem; padding: 2.5rem;
    }}
    h1 {{
      font-family: "Barlow Condensed", sans-serif; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.04em;
      background: linear-gradient(135deg, #00E5FF 0%, #E8EDF5 60%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
      font-size: 2rem; margin: 0 0 1rem;
    }}
    p {{ color: #8899B0; line-height: 1.6; margin: 0 0 1.5rem; }}
    a {{
      display: inline-block; padding: 0.625rem 1.25rem;
      background: #00E5FF; color: #05091D; font-weight: 600;
      border-radius: 0.375rem; text-decoration: none;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Gordie is now open source</h1>
    <p>{OSS_MESSAGE}</p>
    <a href="{GITHUB_URL}">View on GitHub</a>
  </div>
</body>
</html>
"""


def build_app() -> Quart:
    app = Quart(__name__)
    logger = get_logger(__name__, log_file="server.log")

    @app.route("/health", methods=["GET"])
    async def health():
        return jsonify({"status": "ok", "mode": "maintenance"}), 200

    @app.route("/api/signup", methods=["POST", "GET"])
    async def signup_maintenance():
        return jsonify(_oss_payload()), 503

    @app.route("/callback", methods=["GET"])
    async def callback_maintenance():
        return _oss_html(), 503, {"Content-Type": "text/html; charset=utf-8"}

    # Silently consume inbound webhooks so the vendor doesn't retry-storm.
    # The body is dropped — the agent and DB are not running.
    @app.route("/sms/webhook", methods=["POST", "GET"])
    async def sms_webhook_silent():
        logger.info("Maintenance: dropped inbound SMS webhook")
        return jsonify({"status": "accepted"}), 200

    @app.route("/email/webhook", methods=["POST", "GET"])
    async def email_webhook_silent():
        logger.info("Maintenance: dropped inbound email webhook")
        return jsonify({"status": "accepted"}), 200

    @app.errorhandler(404)
    async def catch_all(_err):
        return jsonify(_oss_payload()), 503

    @app.errorhandler(405)
    async def method_not_allowed(_err):
        return jsonify(_oss_payload()), 503

    return app


def main() -> None:
    logger = get_logger(__name__, log_file="server.log")

    host = os.getenv("SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("SERVER_PORT", "8000"))

    logger.info(f"Starting MAINTENANCE server on {host}:{port}...")
    logger.info(f"OSS GitHub URL: {GITHUB_URL}")

    app = build_app()
    config = Config()
    config.bind = [f"{host}:{port}"]
    config.errorlog = logger
    asyncio.run(serve(app, config))


if __name__ == "__main__":
    main()
