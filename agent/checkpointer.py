"""Shared PostgreSQL checkpointer for LangGraph conversation persistence."""

import os

from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import dict_row

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/gordie")

_conn = Connection.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)  # pyright: ignore[reportArgumentType]
checkpointer = PostgresSaver(_conn)  # pyright: ignore[reportArgumentType]
checkpointer.setup()
