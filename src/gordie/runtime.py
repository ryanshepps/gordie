from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import cached_property
from pathlib import Path
from threading import RLock
from typing import cast

from gordie.agent.memory_configuration import ConversationMemory, environment_memory
from gordie.module.model_provider import EnvironmentModels
from gordie.module.statistics import StatisticsFiles
from gordie.plugins import Plugins

_active_runtime: ContextVar[Runtime | None] = ContextVar("gordie_runtime", default=None)


class Runtime:
    def __init__(self, plugins: Plugins) -> None:
        self.plugins = plugins
        self.model_provider = EnvironmentModels(
            os.getenv("LLM_PROVIDER", "openai").lower(),
            os.getenv("LLM_MODEL", "gpt-4o-mini"),
        )
        self.data_directory = Path(
            os.getenv("GORDIE_DATA_DIR", str(Path.home() / ".local/share/gordie"))
        )
        self._resources: dict[str, object] = {}
        self._lock = RLock()

    @cached_property
    def memory(self) -> ConversationMemory:
        return environment_memory()

    @cached_property
    def statistics(self) -> StatisticsFiles:
        return StatisticsFiles(self.data_directory)

    @contextmanager
    def activate(self) -> Iterator[None]:
        token = _active_runtime.set(self)
        try:
            yield
        finally:
            _active_runtime.reset(token)

    def resource[T](self, name: str, factory: Callable[[], T]) -> T:
        with self._lock:
            if name not in self._resources:
                self._resources[name] = factory()
            return cast(T, self._resources[name])

    def run[**P, T](self, function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        with self.activate():
            return function(*args, **kwargs)

    def close(self) -> None:
        with self.activate():
            if self.plugins.communication is not None:
                self.plugins.communication.close()
        if "statistics" in self.__dict__:
            self.statistics.close()
        with self.activate():
            self.plugins.storage.close()
        self._resources.clear()


def current_runtime() -> Runtime:
    runtime = _active_runtime.get()
    if runtime is None:
        raise RuntimeError("Use create_app(plugins) or create_agent(plugins) to run Gordie.")
    return runtime
