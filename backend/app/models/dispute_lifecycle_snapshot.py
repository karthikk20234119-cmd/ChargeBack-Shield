"""
Dispute Lifecycle Snapshot Model — Chargeback Shield Task 5.5

Provides append-only historical audit snapshots for dispute lifecycle state transitions.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base


class DisputeLifecycleSnapshot(Base):
    __tablename__ = "dispute_lifecycle_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id: Mapped[str] = mapped_column(String(64), ForeignKey("disputes.id", ondelete="CASCADE"), index=True)
    razorpay_dispute_id: Mapped[str] = mapped_column(String(64), index=True)
    submission_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    previous_lifecycle_status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    new_lifecycle_status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")

    razorpay_status: Mapped[str] = mapped_column(String(64))
    razorpay_phase: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    razorpay_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    outcome: Mapped[str] = mapped_column(String(32), default="PENDING")
    sync_result: Mapped[str] = mapped_column(String(32), default="STATE_CHANGED")

    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    input_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="lifecycle_snapshots")
