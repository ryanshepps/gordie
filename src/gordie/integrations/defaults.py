import os

from gordie.integrations.postgres import PostgresStorage
from gordie.plugins import Plugins


def default_plugins() -> Plugins:
    return Plugins(
        storage=PostgresStorage(
            os.getenv("DATABASE_URL", "postgresql://localhost:5432/fantasy_agent"),
        ),
    )
