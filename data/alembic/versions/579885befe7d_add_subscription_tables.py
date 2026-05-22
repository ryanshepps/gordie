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
        sa.Column("tier", sa.String(), server_default="free", nullable=False),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("current_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_email"], ["users.email"]),
        sa.PrimaryKeyConstraint("user_email"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_subscriptions")
