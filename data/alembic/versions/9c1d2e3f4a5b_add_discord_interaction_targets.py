"""add discord interaction targets

Revision ID: 9c1d2e3f4a5b
Revises: 7b2c9d0e1f3a
Create Date: 2026-05-23 09:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9c1d2e3f4a5b"
down_revision: str | Sequence[str] | None = "7b2c9d0e1f3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "discord_interaction_targets",
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", sa.Text(), nullable=False),
        sa.Column("interaction_token", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["conversation_threads.id"]),
        sa.PrimaryKeyConstraint("thread_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("discord_interaction_targets")
