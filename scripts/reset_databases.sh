#!/bin/bash

# Resets the PostgreSQL database by dropping ALL tables (including LangGraph
# checkpoint tables) and recreating them via Alembic migrations.

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATABASE_URL="${DATABASE_URL:-postgresql://postgres@localhost:5432/gordie}"

if [ "$1" != "--yes" ]; then
    read -p "This will drop ALL tables (app + LangGraph checkpoints) and recreate them empty. Continue? [y/N] " response
    if [ "$response" != "y" ]; then
        echo "Aborted."
        exit 0
    fi
fi

cd "$PROJECT_ROOT"

echo "Terminating existing connections..."
docker exec gordie-postgres psql -U postgres -d gordie -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'gordie' AND pid <> pg_backend_pid();" \
  > /dev/null 2>&1

echo "Dropping all tables..."
docker exec gordie-postgres psql -U postgres -d gordie -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" || {
    echo "Failed to drop schema. Is the gordie-postgres container running?"
    exit 1
}

echo "Running Alembic migrations..."
uv run alembic upgrade head || {
    echo "Alembic migrations failed."
    exit 1
}

echo "Creating LangGraph checkpoint tables..."
uv run python -c "from agent.checkpointer import checkpointer" || {
    echo "Failed to create checkpoint tables."
    exit 1
}

echo "Done. All tables recreated."
