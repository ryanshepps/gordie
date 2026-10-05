from pathlib import Path
from threading import RLock

import duckdb


class StatisticsFiles:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._connections: dict[str, duckdb.DuckDBPyConnection] = {}
        self._lock = RLock()

    def connection(self, filename: str) -> duckdb.DuckDBPyConnection:
        with self._lock:
            path = self.directory / filename
            if not path.exists():
                raise FileNotFoundError(
                    f"Stats database not found at {path}. Run the stats refresh job."
                )
            if filename not in self._connections:
                self._connections[filename] = duckdb.connect(str(path), read_only=True)
            return self._connections[filename].cursor()

    def reset(self, filename: str) -> None:
        with self._lock:
            connection = self._connections.pop(filename, None)
            if connection is not None:
                connection.close()

    def close(self) -> None:
        for filename in tuple(self._connections):
            self.reset(filename)
