"""add_subscription_tables

Revision ID: 579885befe7d
Revises: 20260215095342
Create Date: 2026-03-03 10:57:36.458654

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "579885befe7d"
down_revision: str | Sequence[str] | None = "20260215095342"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_subscriptions",
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("creem_customer_id", sa.String(), nullable=True),
        sa.Column("creem_subscription_id", sa.String(), nullable=True),
        sa.Column("tier", sa.String(), server_default="trialing", nullable=False),
        sa.Column("status", sa.String(), server_default="trialing", nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_email"], ["users.email"]),
        sa.PrimaryKeyConstraint("user_email"),
    )
    op.create_table(
        "usage_tracking",
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("question_count", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_email"], ["users.email"]),
        sa.PrimaryKeyConstraint("user_email", "week_start"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("usage_tracking")
    op.drop_table("user_subscriptions")
