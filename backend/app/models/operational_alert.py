"""
Operational Alert Database Model — Chargeback Shield Task 6.3

Defines the operational_alerts table for persisting detected operational alerts, SLA tracking,
and exception findings with deterministic fingerprinting.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base


class OperationalAlert(Base):
    __tablename__ = "operational_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id: Mapped[str] = mapped_column(String(64), ForeignKey("disputes.id", ondelete="CASCADE"), index=True)

    category: Mapped[str] = mapped_column(String(32), index=True)  # SLA, HUMAN_REVIEW, SUBMISSION, etc.
    code: Mapped[str] = mapped_column(String(64), index=True)      # HUMAN_REVIEW_REQUIRED, SUBMISSION_STUCK, etc.
    severity: Mapped[str] = mapped_column(String(16), index=True)  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    status: Mapped[str] = mapped_column(String(16), default="OPEN", index=True)  # OPEN, ACKNOWLEDGED, RESOLVED, SUPPRESSED

    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(64))

    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="operational_alerts")
