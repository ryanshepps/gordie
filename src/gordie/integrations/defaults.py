import os
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from gordie.integrations.models import EnvironmentModels
from gordie.integrations.postgres import PostgresStorage
from gordie.module.config import sport_enabled
from gordie.plugins import Plugins
from gordie.scheduled.jobs import register_scheduled_jobs


def default_plugins() -> Plugins:
    plugins = Plugins(
        storage=PostgresStorage(
            os.getenv("DATABASE_URL", "postgresql://localhost:5432/fantasy_agent"),
            Path(os.getenv("GORDIE_DATA_DIR", str(Path.home() / ".local/share/gordie"))),
        ),
        models=EnvironmentModels(
            os.getenv("LLM_PROVIDER", "openai").lower(),
            os.getenv("LLM_MODEL", "gpt-4o-mini"),
        ),
        jobs=(register_default_jobs,),
    )
    if os.getenv("CREEM_API_KEY"):
        from gordie.integrations.creem.plugin import with_creem

        return with_creem(plugins)
    return plugins


def register_default_jobs(scheduler: BackgroundScheduler) -> None:
    register_scheduled_jobs(scheduler)
    for sport, job_id in (("nhl", "refresh_stats_db"), ("mlb", "refresh_mlb_stats_db")):
        if sport_enabled(sport):
            job = scheduler.get_job(job_id)
            if job is not None:
                job.modify(next_run_time=datetime.now(UTC))
