#!/bin/bash

# Script to run DuckDB locally
# This script starts DuckDB with the data directory mounted

# Get the project root directory (parent of scripts/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"

# Create data directory if it doesn't exist
mkdir -p "$DATA_DIR"

# Check if DuckDB is installed
if ! command -v duckdb &> /dev/null; then
    echo "Error: DuckDB is not installed."
    echo "Please install DuckDB from: https://duckdb.org/docs/installation/"
    echo ""
    echo "Quick install options:"
    echo "  macOS (Homebrew): brew install duckdb"
    echo "  Linux: wget https://github.com/duckdb/duckdb/releases/latest/download/duckdb_cli-linux-amd64.zip && unzip duckdb_cli-linux-amd64.zip"
    exit 1
fi

# Change to data directory
cd "$DATA_DIR"

# Start DuckDB
echo "Starting DuckDB in: $DATA_DIR"
echo "Use Ctrl+D or .quit to exit"
echo ""

duckdb nhl_stats.db
