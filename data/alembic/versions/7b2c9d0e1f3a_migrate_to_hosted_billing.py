"""migrate to hosted billing

Revision ID: 7b2c9d0e1f3a
Revises: 6a1f0d2c3b4e
Create Date: 2026-05-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7b2c9d0e1f3a"
down_revision: str | Sequence[str] | None = "6a1f0d2c3b4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        UPDATE user_subscriptions
        SET tier = 'free'
        WHERE tier IN ('trialing', 'standard', 'allstar')
        """
    )
    op.execute(
        """
        UPDATE user_subscriptions
        SET status = 'active'
        WHERE status = 'trialing'
        """
    )
    op.alter_column(
        "user_subscriptions",
        "tier",
        existing_type=sa.String(),
        existing_nullable=False,
        server_default="free",
    )
    op.alter_column(
        "user_subscriptions",
        "status",
        existing_type=sa.String(),
        existing_nullable=False,
        server_default="active",
    )
    op.drop_table("usage_tracking")
    op.drop_column("user_subscriptions", "trial_ends_at")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "user_subscriptions",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "usage_tracking",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("question_count", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "week_start"),
    )
    op.alter_column(
        "user_subscriptions",
        "status",
        existing_type=sa.String(),
        existing_nullable=False,
        server_default="trialing",
    )
    op.alter_column(
        "user_subscriptions",
        "tier",
        existing_type=sa.String(),
        existing_nullable=False,
        server_default="trialing",
    )
