"""Prelaunch database baseline."""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261006"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

medium = postgresql.ENUM(
    "email", "sms", "web", "telegram", "discord", name="medium", create_type=False
)
uuid = postgresql.UUID(as_uuid=True)


def created_at() -> sa.Column[datetime]:
    return sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    medium.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        created_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "yahoo_leagues",
        sa.Column("league_id", sa.String(), nullable=False),
        sa.Column("game_key", sa.String(), nullable=False),
        sa.Column("league_name", sa.String(), nullable=False),
        sa.Column("league_type", sa.String(), nullable=False),
        sa.Column("league_settings", sa.String(), nullable=False),
        created_at(),
        sa.PrimaryKeyConstraint("league_id"),
    )
    op.create_table(
        "user_identities",
        sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("medium", medium, nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text()),
        created_at(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("medium", "external_id", name="uq_user_identity_medium_external_id"),
    )
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])
    op.create_table(
        "conversation_threads",
        sa.Column("id", uuid, nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("medium", medium, nullable=False),
        created_at(),
        sa.Column("last_active", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "medium", name="uq_conversation_threads_user_medium"),
    )
    op.create_index("ix_conversation_threads_user_id", "conversation_threads", ["user_id"])
    op.create_table(
        "conversation_summaries",
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("key_topics", sa.Text()),
        sa.Column("players_mentioned", sa.Text()),
        sa.Column("decisions_made", sa.Text()),
        created_at(),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("thread_id"),
    )
    op.create_index("idx_conversation_summaries_user_id", "conversation_summaries", ["user_id"])
    op.create_table(
        "pending_oauth",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("nonce", sa.String(), nullable=False),
        sa.Column("medium", medium, nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        created_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "yahoo_tokens",
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("yahoo_email", sa.String(), nullable=False),
        sa.Column("access_token", sa.String(), nullable=False),
        sa.Column("refresh_token", sa.String(), nullable=False),
        sa.Column("token_time", sa.DateTime(), nullable=False),
        sa.Column("token_type", sa.String(), server_default="Bearer", nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "yahoo_user_teams",
        sa.Column("league_id", sa.String(), nullable=False),
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("team_name", sa.String(), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(["league_id"], ["yahoo_leagues.league_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("league_id", "team_id", "user_id"),
    )
    op.execute("CREATE SEQUENCE conversation_messages_id_seq AS integer")
    op.create_table(
        "conversation_messages",
        sa.Column(
            "id",
            sa.Integer(),
            server_default=sa.text("nextval('conversation_messages_id_seq'::regclass)"),
            nullable=False,
        ),
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("checkpoint_id", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(50), server_default="standard", nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("ALTER SEQUENCE conversation_messages_id_seq OWNED BY conversation_messages.id")
    op.create_index("idx_conv_msgs_thread", "conversation_messages", ["thread_id", "created_at"])
    op.create_index(
        "idx_conv_msgs_thread_checkpoint", "conversation_messages", ["thread_id", "checkpoint_id"]
    )
    op.create_table(
        "conversation_checkpoints",
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("checkpoint_ns", sa.String(255), server_default="", nullable=False),
        sa.Column("checkpoint_id", sa.String(255), nullable=False),
        sa.Column("parent_checkpoint_id", sa.String(255)),
        sa.Column("channel_values", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id"),
    )
    op.create_index(
        "idx_checkpoints_thread",
        "conversation_checkpoints",
        ["thread_id", "checkpoint_ns", "created_at"],
    )
    op.create_table(
        "conversation_writes",
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("checkpoint_ns", sa.String(255), server_default="", nullable=False),
        sa.Column("checkpoint_id", sa.String(255), nullable=False),
        sa.Column("task_id", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(255), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "channel"
        ),
    )


def downgrade() -> None:
    op.drop_table("conversation_writes")
    op.drop_index("idx_checkpoints_thread", table_name="conversation_checkpoints")
    op.drop_table("conversation_checkpoints")
    op.drop_index("idx_conv_msgs_thread_checkpoint", table_name="conversation_messages")
    op.drop_index("idx_conv_msgs_thread", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_table("yahoo_user_teams")
    op.drop_table("yahoo_tokens")
    op.drop_table("pending_oauth")
    op.drop_index("idx_conversation_summaries_user_id", table_name="conversation_summaries")
    op.drop_table("conversation_summaries")
    op.drop_index("ix_conversation_threads_user_id", table_name="conversation_threads")
    op.drop_table("conversation_threads")
    op.drop_index("ix_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")
    op.drop_table("yahoo_leagues")
    op.drop_table("users")
    medium.drop(op.get_bind(), checkfirst=True)
