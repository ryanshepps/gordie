"""SQLAlchemy declarative models for all database tables."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Medium(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    WEB = "web"
    TELEGRAM = "telegram"
    DISCORD = "discord"


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
    opted_out: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
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
    user_email: Mapped[str] = mapped_column(String, primary_key=True)
    team_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class YahooToken(Base):
    __tablename__ = "yahoo_tokens"

    user_email: Mapped[str] = mapped_column(String, primary_key=True)
    yahoo_email: Mapped[str] = mapped_column(String, nullable=False)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token: Mapped[str] = mapped_column(String, nullable=False)
    token_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    token_type: Mapped[str] = mapped_column(String, nullable=False, server_default="Bearer")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EmailThread(Base):
    __tablename__ = "email_threads"
    __table_args__ = (
        Index("idx_email_threads_thread_id", "thread_id"),
        Index("idx_email_threads_user_email", "user_email"),
    )

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    thread_id: Mapped[str] = mapped_column(String, nullable=False)
    user_email: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class NotificationType(Base):
    __tablename__ = "notification_types"

    type_key: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_email: Mapped[str] = mapped_column(String, primary_key=True)
    league_id: Mapped[str] = mapped_column(
        String, ForeignKey("yahoo_leagues.league_id"), primary_key=True
    )
    notification_type: Mapped[str] = mapped_column(
        String, ForeignKey("notification_types.type_key"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    __table_args__ = (Index("idx_conversation_summaries_user_email", "user_email"),)

    thread_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_email: Mapped[str] = mapped_column(String, nullable=False)
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


class PendingUser(Base):
    __tablename__ = "pending_users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    phone_number: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProcessedInboundMessage(Base):
    __tablename__ = "processed_inbound_messages"
    __table_args__ = (
        UniqueConstraint(
            "medium",
            "external_message_id",
            name="uq_processed_inbound_messages_medium_external_message_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    medium: Mapped[str] = mapped_column(String, nullable=False)
    external_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    external_sender_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    user_email: Mapped[str] = mapped_column(String, primary_key=True)
    creem_customer_id: Mapped[str | None] = mapped_column(String)
    creem_subscription_id: Mapped[str | None] = mapped_column(String)
    tier: Mapped[str] = mapped_column(String, nullable=False, server_default="trialing")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="trialing")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    digest_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UsageTracking(Base):
    __tablename__ = "usage_tracking"

    user_email: Mapped[str] = mapped_column(String, primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class DigestInjuryState(Base):
    __tablename__ = "digest_injury_states"

    user_email: Mapped[str] = mapped_column(String, primary_key=True)
    player_name: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
