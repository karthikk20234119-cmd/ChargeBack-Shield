"""
Dispute Synchronization Audit Trail — Task 3.2

Persistent audit record for every synchronization attempt.
Records source, action, changed fields, conflicts, and sanitized data.
Never stores credentials or authorization headers.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class DisputeSyncAudit(Base):
    __tablename__ = "dispute_sync_audits"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dispute_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("disputes.id", ondelete="CASCADE"),
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(32), default="api_sync"
    )  # "api_sync" or "webhook"
    action: Mapped[str] = mapped_column(
        String(32), index=True
    )  # CREATED, UPDATED, UNCHANGED, CONFLICT
    changed_fields: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # List of field names
    conflicts: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # List of conflict dicts
    raw_razorpay_data: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Sanitized Razorpay response (no credentials, no evidence)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
