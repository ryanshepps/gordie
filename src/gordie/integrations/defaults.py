import os

from gordie.integrations.postgres import PostgresStorage
from gordie.plugins import Plugins


def default_plugins() -> Plugins:
    plugins = Plugins(
        storage=PostgresStorage(
            os.getenv("DATABASE_URL", "postgresql://localhost:5432/fantasy_agent"),
        ),
    )
    if os.getenv("CREEM_API_KEY"):
        from gordie.integrations.creem.plugin import with_creem

        return with_creem(plugins)
    return plugins
