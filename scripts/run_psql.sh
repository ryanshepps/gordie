#!/bin/bash

# Script to connect to the local PostgreSQL database

# Default connection parameters (match docker-compose.yml)
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-gordie}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "Error: psql is not installed."
    echo "Install via: brew install libpq && brew link --force libpq"
    exit 1
fi

echo "Connecting to $DB_NAME on $DB_HOST:$DB_PORT as $DB_USER"
echo "Use \\q to exit"
echo ""

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
