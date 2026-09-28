"""SQLAlchemy declarative models for all database tables."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Medium(StrEnum):
    EMAIL = "email"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserIdentity(Base):
    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("medium", "external_id", name="uq_user_identity_medium_external_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    medium: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ConversationThread(Base):
    __tablename__ = "conversation_threads"
    __table_args__ = (
        UniqueConstraint("user_id", "medium", name="uq_conversation_threads_user_medium"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    medium: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_active: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class YahooLeague(Base):
    __tablename__ = "yahoo_leagues"

    league_id: Mapped[str] = mapped_column(String, primary_key=True)
    game_key: Mapped[str] = mapped_column(String, nullable=False)
    league_name: Mapped[str] = mapped_column(String, nullable=False)
    league_type: Mapped[str] = mapped_column(String, nullable=False)
    league_settings: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class YahooUserTeam(Base):
    __tablename__ = "yahoo_user_teams"

    league_id: Mapped[str] = mapped_column(
        String, ForeignKey("yahoo_leagues.league_id"), primary_key=True
    )
    team_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    team_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class YahooToken(Base):
    __tablename__ = "yahoo_tokens"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    yahoo_email: Mapped[str] = mapped_column(String, nullable=False)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token: Mapped[str] = mapped_column(String, nullable=False)
    token_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    token_type: Mapped[str] = mapped_column(String, nullable=False, server_default="Bearer")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    __table_args__ = (Index("idx_conversation_summaries_user_id", "user_id"),)

    thread_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text)
    key_topics: Mapped[str | None] = mapped_column(Text)
    players_mentioned: Mapped[str | None] = mapped_column(Text)
    decisions_made: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PendingOAuth(Base):
    __tablename__ = "pending_oauth"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    nonce: Mapped[str] = mapped_column(String, nullable=False)
    medium: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    thread_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    creem_customer_id: Mapped[str | None] = mapped_column(String)
    creem_subscription_id: Mapped[str | None] = mapped_column(String)
    tier: Mapped[str] = mapped_column(String, nullable=False, server_default="free")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    current_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
