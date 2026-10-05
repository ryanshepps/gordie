import os
from pathlib import Path


def data_path(filename: str) -> Path:
    directory = Path(os.environ.get("GORDIE_DATA_DIR", Path.home() / ".local/share/gordie"))
    return directory / filename
