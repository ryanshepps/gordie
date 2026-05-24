"""add temporary trial sessions

Revision ID: 3f9b6e7a8c2d
Revises: 9c1d2e3f4a5b
Create Date: 2026-05-24 09:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3f9b6e7a8c2d"
down_revision: str | Sequence[str] | None = "9c1d2e3f4a5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "temporary_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_token_hash", sa.String(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("question_limit", sa.Integer(), server_default="5", nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("converted_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token_hash"),
    )
    op.create_index(
        op.f("ix_temporary_sessions_expires_at"),
        "temporary_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_temporary_sessions_user_id"),
        "temporary_sessions",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "fantasy_provider_connections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_user_id", sa.Text(), nullable=False),
        sa.Column("provider_email", sa.String(), nullable=True),
        sa.Column("temporary_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("question_limit", sa.Integer(), server_default="5", nullable=False),
        sa.Column("connected_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["temporary_session_id"], ["temporary_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_fantasy_provider_connections_provider_user",
        ),
    )
    op.create_index(
        "idx_fantasy_provider_connections_session",
        "fantasy_provider_connections",
        ["temporary_session_id"],
        unique=False,
    )
    op.create_index(
        "idx_fantasy_provider_connections_user",
        "fantasy_provider_connections",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "temporary_chat_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("temporary_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["temporary_session_id"], ["temporary_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_temporary_chat_messages_expires_at"),
        "temporary_chat_messages",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_temporary_chat_messages_temporary_session_id"),
        "temporary_chat_messages",
        ["temporary_session_id"],
        unique=False,
    )

    op.create_table(
        "temporary_session_save_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("temporary_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["temporary_session_id"], ["temporary_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_temporary_session_save_links_email"),
        "temporary_session_save_links",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_temporary_session_save_links_expires_at"),
        "temporary_session_save_links",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_temporary_session_save_links_temporary_session_id"),
        "temporary_session_save_links",
        ["temporary_session_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_temporary_session_save_links_temporary_session_id"),
        table_name="temporary_session_save_links",
    )
    op.drop_index(
        op.f("ix_temporary_session_save_links_expires_at"),
        table_name="temporary_session_save_links",
    )
    op.drop_index(
        op.f("ix_temporary_session_save_links_email"),
        table_name="temporary_session_save_links",
    )
    op.drop_table("temporary_session_save_links")
    op.drop_index(
        op.f("ix_temporary_chat_messages_temporary_session_id"),
        table_name="temporary_chat_messages",
    )
    op.drop_index(
        op.f("ix_temporary_chat_messages_expires_at"), table_name="temporary_chat_messages"
    )
    op.drop_table("temporary_chat_messages")
    op.drop_index(
        "idx_fantasy_provider_connections_user", table_name="fantasy_provider_connections"
    )
    op.drop_index(
        "idx_fantasy_provider_connections_session",
        table_name="fantasy_provider_connections",
    )
    op.drop_table("fantasy_provider_connections")
    op.drop_index(op.f("ix_temporary_sessions_user_id"), table_name="temporary_sessions")
    op.drop_index(op.f("ix_temporary_sessions_expires_at"), table_name="temporary_sessions")
    op.drop_table("temporary_sessions")
