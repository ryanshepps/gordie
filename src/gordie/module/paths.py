from pathlib import Path

from gordie.runtime import current_runtime


def data_path(filename: str) -> Path:
    return current_runtime().plugins.storage.data_path(filename)
