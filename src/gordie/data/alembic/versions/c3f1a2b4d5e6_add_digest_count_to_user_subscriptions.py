"""add digest_count to user_subscriptions

Revision ID: c3f1a2b4d5e6
Revises: 579885befe7d
Create Date: 2026-03-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f1a2b4d5e6"
down_revision: str | Sequence[str] | None = "579885befe7d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_subscriptions",
        sa.Column("digest_count", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user_subscriptions", "digest_count")
