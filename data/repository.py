"""Generic repository base class for database operations."""

from typing import Any

import duckdb


class Repository:
    """Base repository class for CRUD operations on any table."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, table_name: str):
        """Initialize repository with connection and table name.

        Args:
            conn: DuckDB connection
            table_name: Name of the table this repository manages
        """
        self.conn = conn
        self.table_name = table_name

    def insert(self, **kwargs) -> None:
        """Insert a record with any number of fields.

        Args:
            **kwargs: Column names and values to insert

        Example:
            repo.insert(email='user@example.com', name='John')
        """
        columns = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?" for _ in kwargs])
        values = list(kwargs.values())

        self.conn.execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})", values
        )
        self.conn.commit()

    def get_by(self, **filters: Any) -> tuple[Any, ...] | None:
        """Get a single record by filter conditions.

        Args:
            **filters: Column names and values to filter by

        Returns:
            First matching record or None

        Example:
            repo.get_by(email='user@example.com')
        """
        where_clause = " AND ".join([f"{k} = ?" for k in filters])
        values = list(filters.values())

        result = self.conn.execute(
            f"SELECT * FROM {self.table_name} WHERE {where_clause}", values
        ).fetchone()
        return result

    def get_all(self, **filters: Any) -> list[tuple[Any, ...]]:
        """Get all records matching filter conditions.

        Args:
            **filters: Column names and values to filter by (optional)

        Returns:
            List of matching records

        Example:
            repo.get_all(user_email='user@example.com')
            repo.get_all()  # Get all records
        """
        if filters:
            where_clause = " AND ".join([f"{k} = ?" for k in filters])
            values = list(filters.values())
            return self.conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {where_clause}", values
            ).fetchall()
        return self.conn.execute(f"SELECT * FROM {self.table_name}").fetchall()

    def update(self, filters: dict[str, Any], **updates: Any) -> None:
        """Update records matching filters.

        Args:
            filters: Dict of column names and values to identify records
            **updates: Column names and new values to update

        Example:
            repo.update({'email': 'old@example.com'}, email='new@example.com')
        """
        set_clause = ", ".join([f"{k} = ?" for k in updates])
        where_clause = " AND ".join([f"{k} = ?" for k in filters])
        values = list(updates.values()) + list(filters.values())

        self.conn.execute(f"UPDATE {self.table_name} SET {set_clause} WHERE {where_clause}", values)
        self.conn.commit()

    def delete(self, **filters) -> None:
        """Delete records matching filters.

        Args:
            **filters: Column names and values to filter by

        Example:
            repo.delete(email='user@example.com')
        """
        where_clause = " AND ".join([f"{k} = ?" for k in filters])
        values = list(filters.values())

        self.conn.execute(f"DELETE FROM {self.table_name} WHERE {where_clause}", values)
        self.conn.commit()

    def upsert(self, conflict_columns: list[str], **values) -> None:
        """Insert or update a record if it already exists.

        Args:
            conflict_columns: Columns that define uniqueness (for conflict detection)
            **values: Column names and values to insert/update

        Example:
            repo.upsert(['email'], email='user@example.com', name='John')
        """
        columns = ", ".join(values.keys())
        placeholders = ", ".join(["?" for _ in values])
        update_clause = ", ".join(
            [f"{k} = EXCLUDED.{k}" for k in values if k not in conflict_columns]
        )
        conflict_clause = ", ".join(conflict_columns)

        self.conn.execute(
            f"""
            INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})
            ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_clause}
            """,
            list(values.values()),
        )
        self.conn.commit()
