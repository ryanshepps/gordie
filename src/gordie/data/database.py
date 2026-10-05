from sqlalchemy.orm import Session

from gordie.runtime import current_runtime


def get_session() -> Session:
    return current_runtime().plugins.storage.session()
