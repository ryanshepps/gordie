"""SQLAlchemy declarative models for all database tables."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, primary_key=True)
    phone_number: Mapped[str | None] = mapped_column(String, unique=True)
    sms_opted_out: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


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
    user_email: Mapped[str] = mapped_column(String, ForeignKey("users.email"), primary_key=True)
    team_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class YahooToken(Base):
    __tablename__ = "yahoo_tokens"

    user_email: Mapped[str] = mapped_column(String, ForeignKey("users.email"), primary_key=True)
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
    user_email: Mapped[str] = mapped_column(String, ForeignKey("users.email"), nullable=False)
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

    user_email: Mapped[str] = mapped_column(String, ForeignKey("users.email"), primary_key=True)
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
    __table_args__ = (
        CheckConstraint(
            "user_email IS NOT NULL OR phone_number IS NOT NULL",
            name="ck_pending_oauth_has_identifier",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    nonce: Mapped[str] = mapped_column(String, nullable=False)
    user_email: Mapped[str | None] = mapped_column(String)
    phone_number: Mapped[str | None] = mapped_column(String)
    thread_id: Mapped[str] = mapped_column(String, nullable=False)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PendingUser(Base):
    __tablename__ = "pending_users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    phone_number: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SmsThread(Base):
    __tablename__ = "sms_threads"

    thread_id: Mapped[str] = mapped_column(String, primary_key=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=False, index=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProcessedSms(Base):
    __tablename__ = "processed_sms"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProcessedEmail(Base):
    __tablename__ = "processed_emails"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    sender_email: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    user_email: Mapped[str] = mapped_column(String, ForeignKey("users.email"), primary_key=True)
    creem_customer_id: Mapped[str | None] = mapped_column(String)
    creem_subscription_id: Mapped[str | None] = mapped_column(String)
    tier: Mapped[str] = mapped_column(String, nullable=False, server_default="free")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    current_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    digest_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DigestInjuryState(Base):
    __tablename__ = "digest_injury_states"

    user_email: Mapped[str] = mapped_column(String, ForeignKey("users.email"), primary_key=True)
    player_name: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
