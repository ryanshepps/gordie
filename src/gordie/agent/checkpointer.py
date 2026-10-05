from langgraph.checkpoint.base import BaseCheckpointSaver

from gordie.runtime import current_runtime


def get_checkpointer() -> BaseCheckpointSaver[str]:
    return current_runtime().plugins.storage.checkpoint()
