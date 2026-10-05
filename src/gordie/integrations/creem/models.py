from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from gordie.data.models import Base


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
