# Database Setup

Gordie uses Postgres for application state (users, OAuth tokens, and conversation state) and for LangGraph conversation checkpoints.

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

Migrations live in `src/gordie/data/alembic/versions/`.

```bash
uv run alembic upgrade head                      # apply
uv run alembic revision --autogenerate -m "..."  # generate new
uv run alembic downgrade -1                      # revert one
```

## LangGraph checkpoint tables

Gordie's custom checkpointer uses the conversation tables managed by Alembic.
Importing the package does not create tables. The server applies migrations before startup.

## Reset everything

```bash
docker compose down -v       # drops the postgres volume
docker compose up -d
```

There's a helper script: `scripts/reset_databases.sh` (assumes `gordie-postgres` container).

## Production

For production, point `DATABASE_URL` at a managed Postgres (Neon, Supabase, RDS, etc.).
Back up the Yahoo token and conversation tables, and persist the statistics directory
configured by `GORDIE_DATA_DIR` separately.
