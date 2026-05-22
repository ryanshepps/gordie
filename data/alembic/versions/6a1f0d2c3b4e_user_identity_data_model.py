"""user identity data model

Revision ID: 6a1f0d2c3b4e
Revises: 95fa85515d15
Create Date: 2026-05-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6a1f0d2c3b4e"
down_revision: str | Sequence[str] | None = "95fa85515d15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

medium_enum = postgresql.ENUM(
    "email",
    "sms",
    "web",
    "telegram",
    "discord",
    name="medium",
    create_type=False,
)


def _replace_user_email_with_user_id(
    table_name: str,
    primary_key_columns: Sequence[str] | None = None,
    old_index_name: str | None = None,
    new_index_name: str | None = None,
) -> None:
    op.execute(f"DELETE FROM {table_name}")
    if old_index_name:
        op.drop_index(old_index_name, table_name=table_name)
    if primary_key_columns:
        op.drop_constraint(f"{table_name}_pkey", table_name, type_="primary")
    op.add_column(
        table_name,
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.drop_column(table_name, "user_email")
    op.create_foreign_key(
        f"{table_name}_user_id_fkey",
        table_name,
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    if primary_key_columns:
        op.create_primary_key(f"{table_name}_pkey", table_name, list(primary_key_columns))
    if new_index_name:
        op.create_index(new_index_name, table_name, ["user_id"], unique=False)


def _restore_user_email_column(
    table_name: str,
    primary_key_columns: Sequence[str] | None = None,
    old_index_name: str | None = None,
    new_index_name: str | None = None,
) -> None:
    op.execute(f"DELETE FROM {table_name}")
    if old_index_name:
        op.drop_index(old_index_name, table_name=table_name)
    op.drop_constraint(f"{table_name}_user_id_fkey", table_name, type_="foreignkey")
    if primary_key_columns:
        op.drop_constraint(f"{table_name}_pkey", table_name, type_="primary")
    op.add_column(table_name, sa.Column("user_email", sa.String(), nullable=False))
    op.drop_column(table_name, "user_id")
    if primary_key_columns:
        op.create_primary_key(f"{table_name}_pkey", table_name, list(primary_key_columns))
    if new_index_name:
        op.create_index(new_index_name, table_name, ["user_email"], unique=False)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    medium_enum.create(op.get_bind(), checkfirst=True)

    op.drop_constraint("yahoo_user_teams_user_email_fkey", "yahoo_user_teams", type_="foreignkey")
    op.drop_constraint("yahoo_tokens_user_email_fkey", "yahoo_tokens", type_="foreignkey")
    op.drop_constraint("email_threads_user_email_fkey", "email_threads", type_="foreignkey")
    op.drop_constraint(
        "notification_preferences_user_email_fkey",
        "notification_preferences",
        type_="foreignkey",
    )
    op.drop_constraint(
        "user_subscriptions_user_email_fkey", "user_subscriptions", type_="foreignkey"
    )
    op.drop_constraint("usage_tracking_user_email_fkey", "usage_tracking", type_="foreignkey")
    op.drop_constraint(
        "digest_injury_states_user_email_fkey", "digest_injury_states", type_="foreignkey"
    )

    op.drop_table("users")
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user_identities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medium", medium_enum, nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("opted_out", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("medium", "external_id", name="uq_user_identity_medium_external_id"),
    )
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"], unique=False)

    _replace_user_email_with_user_id("yahoo_user_teams", ["league_id", "team_id", "user_id"])
    _replace_user_email_with_user_id("yahoo_tokens", ["user_id"])
    _replace_user_email_with_user_id(
        "email_threads",
        old_index_name="idx_email_threads_user_email",
        new_index_name="idx_email_threads_user_id",
    )
    _replace_user_email_with_user_id(
        "notification_preferences",
        ["user_id", "league_id", "notification_type"],
    )
    _replace_user_email_with_user_id(
        "conversation_summaries",
        old_index_name="idx_conversation_summaries_user_email",
        new_index_name="idx_conversation_summaries_user_id",
    )
    _replace_user_email_with_user_id("user_subscriptions", ["user_id"])
    _replace_user_email_with_user_id("usage_tracking", ["user_id", "week_start"])
    _replace_user_email_with_user_id("digest_injury_states", ["user_id", "player_name"])

    op.create_table(
        "conversation_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("medium", medium_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_active", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "medium", name="uq_conversation_threads_user_medium"),
    )
    op.create_index(
        "ix_conversation_threads_user_id", "conversation_threads", ["user_id"], unique=False
    )

    op.drop_table("sms_threads")
    op.drop_table("web_threads")

    op.drop_table("pending_oauth")
    op.create_table(
        "pending_oauth",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("nonce", sa.String(), nullable=False),
        sa.Column("medium", medium_enum, nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.drop_table("processed_sms")
    op.drop_table("processed_emails")
    op.create_table(
        "processed_inbound_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("medium", medium_enum, nullable=False),
        sa.Column("external_message_id", sa.Text(), nullable=False),
        sa.Column("external_sender_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "medium",
            "external_message_id",
            name="uq_processed_inbound_messages_medium_external_message_id",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("processed_inbound_messages")
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

    op.drop_table("pending_oauth")
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

    op.create_table(
        "web_threads",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sms_threads",
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("phone_number", sa.String(), nullable=False),
        sa.Column(
            "last_message_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("thread_id"),
    )
    op.create_index(
        op.f("ix_sms_threads_phone_number"), "sms_threads", ["phone_number"], unique=False
    )

    op.drop_index("ix_conversation_threads_user_id", table_name="conversation_threads")
    op.drop_table("conversation_threads")

    _restore_user_email_column("digest_injury_states", ["user_email", "player_name"])
    _restore_user_email_column("usage_tracking", ["user_email", "week_start"])
    _restore_user_email_column("user_subscriptions", ["user_email"])
    _restore_user_email_column(
        "conversation_summaries",
        old_index_name="idx_conversation_summaries_user_id",
        new_index_name="idx_conversation_summaries_user_email",
    )
    _restore_user_email_column(
        "notification_preferences",
        ["user_email", "league_id", "notification_type"],
    )
    _restore_user_email_column(
        "email_threads",
        old_index_name="idx_email_threads_user_id",
        new_index_name="idx_email_threads_user_email",
    )
    _restore_user_email_column("yahoo_tokens", ["user_email"])
    _restore_user_email_column("yahoo_user_teams", ["league_id", "team_id", "user_email"])

    op.drop_index("ix_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")
    op.drop_table("users")
    op.create_table(
        "users",
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("sms_opted_out", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("email"),
        sa.UniqueConstraint("phone_number", name="uq_users_phone_number"),
    )

    medium_enum.drop(op.get_bind(), checkfirst=True)
