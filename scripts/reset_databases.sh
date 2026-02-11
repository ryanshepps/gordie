#!/bin/bash

# Resets the PostgreSQL database by running Alembic migrations from scratch

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ "$1" != "--yes" ]; then
    read -p "This will drop all tables and recreate them empty. Continue? [y/N] " response
    if [ "$response" != "y" ]; then
        echo "Aborted."
        exit 0
    fi
fi

cd "$PROJECT_ROOT"
uv run alembic downgrade base && uv run alembic upgrade head

echo "Done."
