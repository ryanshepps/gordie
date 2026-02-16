"""Add conversation tables for custom checkpointer

Revision ID: 20260215095342
Revises: b852f0a5c7c5
Create Date: 2026-02-15 09:53:42.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260215095342"
down_revision: str | Sequence[str] | None = "b852f0a5c7c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade():
    # Conversation messages - primary source of truth for web view
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("checkpoint_id", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_conv_msgs_thread", "conversation_messages", ["thread_id", "created_at"], unique=False
    )
    op.create_index(
        "idx_conv_msgs_thread_checkpoint",
        "conversation_messages",
        ["thread_id", "checkpoint_id"],
        unique=False,
    )

    # Checkpoint state for LangGraph execution
    op.create_table(
        "conversation_checkpoints",
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("checkpoint_ns", sa.String(255), nullable=False, server_default=""),
        sa.Column("checkpoint_id", sa.String(255), nullable=False),
        sa.Column("parent_checkpoint_id", sa.String(255), nullable=True),
        sa.Column("channel_values", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id"),
    )

    op.create_index(
        "idx_checkpoints_thread",
        "conversation_checkpoints",
        ["thread_id", "checkpoint_ns", "created_at"],
        unique=False,
    )

    # Pending writes for interrupted executions
    op.create_table(
        "conversation_writes",
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("checkpoint_ns", sa.String(255), nullable=False, server_default=""),
        sa.Column("checkpoint_id", sa.String(255), nullable=False),
        sa.Column("task_id", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(255), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "channel"
        ),
    )


def downgrade():
    op.drop_table("conversation_writes")
    op.drop_table("conversation_checkpoints")
    op.drop_table("conversation_messages")
