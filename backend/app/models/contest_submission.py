import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base


class ContestSubmission(Base):
    __tablename__ = "contest_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_attempt_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    dispute_id: Mapped[str] = mapped_column(String(64), ForeignKey("disputes.id", ondelete="CASCADE"), unique=True, index=True)
    contest_draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("contest_drafts.id", ondelete="CASCADE"), index=True)
    preflight_id: Mapped[str] = mapped_column(String(36), ForeignKey("contest_submission_preflights.id", ondelete="CASCADE"), index=True)
    
    input_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    
    previous_state: Mapped[str] = mapped_column(String(32), default="PRECHECK_REQUIRED")
    state: Mapped[str] = mapped_column(String(32), default="SUBMISSION_AUTHORIZED", index=True)
    
    razorpay_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    razorpay_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    failure_category: Mapped[str] = mapped_column(String(32), default="NONE")
    failure_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reconciliation_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="submissions")
    contest_draft: Mapped["ContestDraft"] = relationship("ContestDraft")
    preflight: Mapped["ContestSubmissionPreflight"] = relationship("ContestSubmissionPreflight")
    audits: Mapped[List["ContestSubmissionAudit"]] = relationship("ContestSubmissionAudit", back_populates="submission", cascade="all, delete-orphan")
