from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True) # x-razorpay-event-id
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    dispute_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
