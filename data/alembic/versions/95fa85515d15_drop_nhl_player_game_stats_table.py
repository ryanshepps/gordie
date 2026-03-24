"""drop nhl_player_game_stats table

Revision ID: 95fa85515d15
Revises: d4e5f6a7b8c9
Create Date: 2026-03-24 09:04:47.295189

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '95fa85515d15'
down_revision: str | Sequence[str] | None = 'd4e5f6a7b8c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("nhl_player_game_stats")


def downgrade() -> None:
    op.create_table(
        "nhl_player_game_stats",
        sa.Column("nhl_api_player_id", sa.Integer(), nullable=False),
        sa.Column("nhl_api_game_id", sa.Integer(), nullable=False),
        sa.Column("game_date", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("goals", sa.Integer(), nullable=True),
        sa.Column("assists", sa.Integer(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("plus_minus", sa.Integer(), nullable=True),
        sa.Column("pim", sa.Integer(), nullable=True),
        sa.Column("hits", sa.Integer(), nullable=True),
        sa.Column("power_play_goals", sa.Integer(), nullable=True),
        sa.Column("sog", sa.Integer(), nullable=True),
        sa.Column("faceoff_winning_pctg", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("toi", sa.String(), nullable=True),
        sa.Column("blocked_shots", sa.Integer(), nullable=True),
        sa.Column("shifts", sa.Integer(), nullable=True),
        sa.Column("giveaways", sa.Integer(), nullable=True),
        sa.Column("takeaways", sa.Integer(), nullable=True),
        sa.Column("corsi_for", sa.Integer(), nullable=True),
        sa.Column("fenwick_for", sa.Integer(), nullable=True),
        sa.Column("missed_shots", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("nhl_api_player_id", "nhl_api_game_id"),
    )
