"""Generic repository base class for database operations."""

from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.database import get_session


class Repository:
    """Base repository class for CRUD operations on any table."""

    def __init__(self, table_name: str, session: Session | None = None):
        """Initialize repository with table name and optional session.

        Args:
            table_name: Name of the table this repository manages
            session: Optional SQLAlchemy session. If not provided, creates a new one.
        """
        self._owns_session = session is None
        self.session = session or get_session()
        self.table_name = table_name

    def insert(self, **kwargs) -> None:
        """Insert a record with any number of fields.

        Args:
            **kwargs: Column names and values to insert

        Example:
            repo.insert(email='user@example.com', name='John')
        """
        columns = ", ".join(kwargs.keys())
        placeholders = ", ".join([f":{k}" for k in kwargs])

        self.session.execute(
            text(f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"),
            kwargs,
        )
        self.session.commit()

    def get_by(self, **filters: Any) -> tuple[Any, ...] | None:
        """Get a single record by filter conditions.

        Args:
            **filters: Column names and values to filter by

        Returns:
            First matching record or None

        Example:
            repo.get_by(email='user@example.com')
        """
        where_clause = " AND ".join([f"{k} = :{k}" for k in filters])

        result = self.session.execute(
            text(f"SELECT * FROM {self.table_name} WHERE {where_clause}"),
            filters,
        ).fetchone()
        return cast(tuple[Any, ...] | None, result)

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
            where_clause = " AND ".join([f"{k} = :{k}" for k in filters])
            return cast(
                list[tuple[Any, ...]],
                list(
                    self.session.execute(
                        text(f"SELECT * FROM {self.table_name} WHERE {where_clause}"),
                        filters,
                    ).fetchall()
                ),
            )
        return cast(
            list[tuple[Any, ...]],
            list(self.session.execute(text(f"SELECT * FROM {self.table_name}")).fetchall()),
        )

    def update(self, filters: dict[str, Any], **updates: Any) -> None:
        """Update records matching filters.

        Args:
            filters: Dict of column names and values to identify records
            **updates: Column names and new values to update

        Example:
            repo.update({'email': 'old@example.com'}, email='new@example.com')
        """
        set_clause = ", ".join([f"{k} = :set_{k}" for k in updates])
        where_clause = " AND ".join([f"{k} = :where_{k}" for k in filters])

        params = {f"set_{k}": v for k, v in updates.items()}
        params.update({f"where_{k}": v for k, v in filters.items()})

        self.session.execute(
            text(f"UPDATE {self.table_name} SET {set_clause} WHERE {where_clause}"),
            params,
        )
        self.session.commit()

    def delete(self, **filters) -> None:
        """Delete records matching filters.

        Args:
            **filters: Column names and values to filter by

        Example:
            repo.delete(email='user@example.com')
        """
        where_clause = " AND ".join([f"{k} = :{k}" for k in filters])

        self.session.execute(
            text(f"DELETE FROM {self.table_name} WHERE {where_clause}"),
            filters,
        )
        self.session.commit()

    def upsert(self, conflict_columns: list[str], **values) -> None:
        """Insert or update a record if it already exists.

        Args:
            conflict_columns: Columns that define uniqueness (for conflict detection)
            **values: Column names and values to insert/update

        Example:
            repo.upsert(['email'], email='user@example.com', name='John')
        """
        columns = ", ".join(values.keys())
        placeholders = ", ".join([f":{k}" for k in values])
        update_clause = ", ".join(
            [f"{k} = EXCLUDED.{k}" for k in values if k not in conflict_columns]
        )
        conflict_clause = ", ".join(conflict_columns)

        self.session.execute(
            text(
                f"""
                INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})
                ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_clause}
                """
            ),
            values,
        )
        self.session.commit()

    def close(self) -> None:
        """Close the session if owned by this repository."""
        if self._owns_session and self.session:
            self.session.close()
