"""replace oauth_nonces with pending_oauth

Revision ID: f12a0be9d8aa
Revises: a1f82dd274ec
Create Date: 2026-02-11 13:04:07.081464

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f12a0be9d8aa"
down_revision: str | Sequence[str] | None = "a1f82dd274ec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "pending_oauth",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("nonce", sa.String(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=True),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "user_email IS NOT NULL OR phone_number IS NOT NULL",
            name="ck_pending_oauth_has_identifier",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_table("oauth_nonces")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "oauth_nonces",
        sa.Column("user_email", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("nonce", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("thread_id", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_email", name="oauth_nonces_pkey"),
    )
    op.drop_table("pending_oauth")
