# Database Setup

Gordie uses Postgres for application state (users, OAuth tokens, subscriptions, SMS threads, notification preferences) and for LangGraph conversation checkpoints.

## Local Postgres via Docker

```bash
docker compose up -d
```

The server applies Alembic migrations automatically before it starts accepting requests.

`docker-compose.yml` defaults to:
- DB name: `fantasy_agent`
- User: `postgres`
- Password: `postgres`

Override with `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` env vars in `.env`.

## Migrations

Migrations live in `data/alembic/versions/`.

```bash
uv run alembic upgrade head                      # apply
uv run alembic revision --autogenerate -m "..."  # generate new
uv run alembic downgrade -1                      # revert one
```

## LangGraph checkpoint tables

LangGraph's PostgresSaver auto-creates its own tables on first import of `agent.checkpointer`. There's no Alembic migration for them — they live alongside the app schema. If you wipe + restart, the server recreates them.

## Reset everything

```bash
docker compose down -v       # drops the postgres volume
docker compose up -d
```

There's a helper script: `scripts/reset_databases.sh` (assumes `gordie-postgres` container).

## Production

For production, point `DATABASE_URL` at a managed Postgres (Neon, Supabase, RDS, etc.). The schema works on Postgres 14+. Backups are *your responsibility* — `data/platform.db` (Yahoo tokens) and conversation checkpoints are the highest-value tables; lose them and users have to re-auth and lose their thread history.
