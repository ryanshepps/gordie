#!/bin/bash

# Removes all databases and recreates them from data.schemas

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"

if [ "$1" != "--yes" ]; then
    read -p "This will delete all databases and recreate them empty. Continue? [y/N] " response
    if [ "$response" != "y" ]; then
        echo "Aborted."
        exit 0
    fi
fi

# Remove existing databases
for file in platform.db nhl_stats.db agent_conversations.db agent_conversations.db-shm agent_conversations.db-wal; do
    if [ -f "$DATA_DIR/$file" ]; then
        rm "$DATA_DIR/$file"
        echo "Removed $file"
    fi
done

# Recreate from schemas
cd "$PROJECT_ROOT"
uv run python -m data.schemas
echo "Recreated databases from data.schemas"

echo "Done."
