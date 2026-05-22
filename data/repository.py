"""Generic repository base class for database operations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from data.database import get_session

FilterValue = str | int | float | bool | None | datetime | UUID
DatabaseRow = Row[tuple[object, ...]]


class Repository:
    """Base repository class for CRUD operations on any table."""

    def __init__(self, table_name: str, session: Session | None = None) -> None:
        self._owns_session = session is None
        self.session = session or get_session()
        self.table_name = table_name

    def insert(self, **kwargs: FilterValue) -> None:
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

    def get_by(self, **filters: FilterValue) -> DatabaseRow | None:
        where_clause = " AND ".join([f"{k} = :{k}" for k in filters])

        return self.session.execute(
            text(f"SELECT * FROM {self.table_name} WHERE {where_clause}"),
            filters,
        ).fetchone()

    def get_all(self, **filters: FilterValue) -> list[DatabaseRow]:
        if filters:
            where_clause = " AND ".join([f"{k} = :{k}" for k in filters])
            return list(
                self.session.execute(
                    text(f"SELECT * FROM {self.table_name} WHERE {where_clause}"),
                    filters,
                ).fetchall()
            )
        return list(self.session.execute(text(f"SELECT * FROM {self.table_name}")).fetchall())

    def update(self, filters: dict[str, FilterValue], **updates: FilterValue) -> None:
        set_clause = ", ".join([f"{k} = :set_{k}" for k in updates])
        where_clause = " AND ".join([f"{k} = :where_{k}" for k in filters])

        params = {f"set_{k}": v for k, v in updates.items()}
        params.update({f"where_{k}": v for k, v in filters.items()})

        self.session.execute(
            text(f"UPDATE {self.table_name} SET {set_clause} WHERE {where_clause}"),
            params,
        )
        self.session.commit()

    def delete(self, **filters: FilterValue) -> None:
        where_clause = " AND ".join([f"{k} = :{k}" for k in filters])

        self.session.execute(
            text(f"DELETE FROM {self.table_name} WHERE {where_clause}"),
            filters,
        )
        self.session.commit()

    def upsert(self, conflict_columns: list[str], **values: FilterValue) -> None:
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
