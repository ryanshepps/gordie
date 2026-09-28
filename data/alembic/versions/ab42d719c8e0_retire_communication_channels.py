"""retire communication channel tables

Revision ID: ab42d719c8e0
Revises: 9c1d2e3f4a5b
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ab42d719c8e0"
down_revision: str | Sequence[str] | None = "9c1d2e3f4a5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("discord_interaction_targets")
    op.drop_index("idx_email_threads_thread_id", table_name="email_threads")
    op.drop_index("idx_email_threads_user_id", table_name="email_threads")
    op.drop_table("email_threads")
    op.drop_table("notification_preferences")
    op.drop_table("notification_types")
    op.drop_table("digest_injury_states")
    op.drop_table("pending_users")
    op.drop_table("processed_inbound_messages")
    op.drop_column("user_identities", "opted_out")
    op.drop_column("user_subscriptions", "digest_count")


def downgrade() -> None:
    op.add_column(
        "user_subscriptions",
        sa.Column("digest_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_identities",
        sa.Column("opted_out", sa.Boolean(), nullable=False, server_default="false"),
    )
    medium = postgresql.ENUM(
        "email", "sms", "web", "telegram", "discord", name="medium", create_type=False
    )
    op.create_table(
        "processed_inbound_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("medium", medium, nullable=False),
        sa.Column("external_message_id", sa.Text(), nullable=False),
        sa.Column("external_sender_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "medium",
            "external_message_id",
            name="uq_processed_inbound_messages_medium_external_message_id",
        ),
    )
    op.create_table(
        "pending_users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("phone_number", sa.String()),
        sa.Column("email", sa.String()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_table(
        "digest_injury_states",
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True
        ),
        sa.Column("player_name", sa.String(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_table(
        "notification_types",
        sa.Column("type_key", sa.String(), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("default_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_table(
        "notification_preferences",
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True
        ),
        sa.Column(
            "league_id", sa.String(), sa.ForeignKey("yahoo_leagues.league_id"), primary_key=True
        ),
        sa.Column(
            "notification_type",
            sa.String(),
            sa.ForeignKey("notification_types.type_key"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_table(
        "email_threads",
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("subject", sa.String()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("idx_email_threads_thread_id", "email_threads", ["thread_id"])
    op.create_index("idx_email_threads_user_id", "email_threads", ["user_id"])
    op.create_table(
        "discord_interaction_targets",
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_threads.id"),
            primary_key=True,
        ),
        sa.Column("application_id", sa.Text(), nullable=False),
        sa.Column("interaction_token", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
