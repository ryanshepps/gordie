"""seed notification types

Revision ID: a1f82dd274ec
Revises: e254af7bde01
Create Date: 2026-02-11 11:35:10.534889

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1f82dd274ec'
down_revision: str | Sequence[str] | None = 'e254af7bde01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO notification_types (type_key, display_name, description, default_enabled)
        VALUES (
            'weekly_digest',
            'Weekly Digest',
            'Weekly fantasy hockey summary with roster updates and recommendations',
            TRUE
        )
        ON CONFLICT (type_key) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO notification_types (type_key, display_name, description, default_enabled)
        VALUES (
            'news_digest',
            'Daily News Digest',
            'Daily NHL news alerts for injuries, trades, and favorable matchups',
            TRUE
        )
        ON CONFLICT (type_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM notification_types WHERE type_key IN ('weekly_digest', 'news_digest')")
