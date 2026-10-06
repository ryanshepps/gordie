"""Add phone identities for hosted messaging."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261006_phone"
down_revision: str | Sequence[str] | None = "20261006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE medium ADD VALUE IF NOT EXISTS 'phone'")


def downgrade() -> None:
    pass
