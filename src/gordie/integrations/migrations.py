import logging
from importlib.resources import files

from alembic import command
from alembic.config import Config


def run_migrations(database_url: str | None = None) -> None:
    logger = logging.getLogger(__name__)
    logger.info("Running database migrations...")
    config = Config(str(files("gordie").joinpath("resources/alembic.ini")))
    config.set_main_option("script_location", str(files("gordie").joinpath("data/alembic")))
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    upgrade_database(config, "head")
    logger.info("Database migrations complete.")


def upgrade_database(config: Config, revision: str) -> None:
    command.upgrade(config, revision)
