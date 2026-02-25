"""add multi-channel tables

Revision ID: 512eb4d7a7fb
Revises: f12a0be9d8aa
Create Date: 2026-02-11 14:57:34.355749

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '512eb4d7a7fb'
down_revision: str | Sequence[str] | None = 'f12a0be9d8aa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('pending_users',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('phone_number', sa.String(), nullable=True),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sms_threads',
    sa.Column('thread_id', sa.String(), nullable=False),
    sa.Column('phone_number', sa.String(), nullable=False),
    sa.Column('last_message_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('thread_id')
    )
    op.create_index(op.f('ix_sms_threads_phone_number'), 'sms_threads', ['phone_number'], unique=False)
    op.create_table('web_threads',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('thread_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('users', sa.Column('phone_number', sa.String(), nullable=True))
    op.add_column('users', sa.Column('sms_opted_out', sa.Boolean(), server_default='false', nullable=False))
    op.create_unique_constraint('uq_users_phone_number', 'users', ['phone_number'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_users_phone_number', 'users', type_='unique')
    op.drop_column('users', 'sms_opted_out')
    op.drop_column('users', 'phone_number')
    op.drop_table('web_threads')
    op.drop_index(op.f('ix_sms_threads_phone_number'), table_name='sms_threads')
    op.drop_table('sms_threads')
    op.drop_table('pending_users')
