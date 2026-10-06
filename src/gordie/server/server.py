from __future__ import annotations

import asyncio
import os
import threading

from hypercorn.asyncio import serve
from hypercorn.config import Config

from gordie.application import create_app
from gordie.module.logger import get_logger
from gordie.module.model_provider import DEFAULT_EMBEDDING_DIMENSIONS, DEFAULT_EMBEDDING_MODEL
from gordie.plugins import Plugins

_server_instance: Server | None = None
_server_lock = threading.Lock()


class Server:
    def __init__(self, host: str, port: int, plugins: Plugins | None = None) -> None:
        if plugins is None:
            from gordie.integrations.defaults import default_plugins

            plugins = default_plugins()
        self.host = host
        self.port = port
        self.app = create_app(
            plugins,
            openrouter_api_key=os.environ["OPENROUTER_API_KEY"],
            model=os.environ["LLM_MODEL"],
            embedding_model=os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            embedding_dimensions=int(
                os.getenv("EMBEDDING_DIMENSIONS", str(DEFAULT_EMBEDDING_DIMENSIONS))
            ),
        )

    def run(self) -> None:
        config = Config()
        config.bind = [f"{self.host}:{self.port}"]
        config.errorlog = get_logger(__name__, log_file="server.log")
        asyncio.run(serve(self.app, config))


def start_server(host: str = "localhost", port: int = 8000) -> None:
    global _server_instance
    with _server_lock:
        if _server_instance is None:
            _server_instance = Server(host, port)
            threading.Thread(target=_server_instance.run, daemon=True).start()


def get_server_url() -> str:
    if _server_instance:
        return f"http://{_server_instance.host}:{_server_instance.port}"
    return "http://localhost:8000"
