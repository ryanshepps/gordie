"""add processed message tables

Revision ID: b852f0a5c7c5
Revises: 512eb4d7a7fb
Create Date: 2026-02-11 15:44:17.091494

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b852f0a5c7c5"
down_revision: str | Sequence[str] | None = "512eb4d7a7fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "processed_emails",
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("sender_email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_table(
        "processed_sms",
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("phone_number", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("message_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("processed_sms")
    op.drop_table("processed_emails")
