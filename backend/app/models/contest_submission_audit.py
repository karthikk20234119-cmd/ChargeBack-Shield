import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base


class ContestSubmissionAudit(Base):
    __tablename__ = "contest_submission_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id: Mapped[str] = mapped_column(String(64), ForeignKey("disputes.id", ondelete="CASCADE"), index=True)
    contest_submission_id: Mapped[str] = mapped_column(String(36), ForeignKey("contest_submissions.id", ondelete="CASCADE"), index=True)
    
    contest_draft_id: Mapped[str] = mapped_column(String(36))
    preflight_id: Mapped[str] = mapped_column(String(36))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    
    previous_state: Mapped[str] = mapped_column(String(32))
    new_state: Mapped[str] = mapped_column(String(32))
    submission_status: Mapped[str] = mapped_column(String(32))
    
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    razorpay_reference_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sanitized_response_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    submission: Mapped["ContestSubmission"] = relationship("ContestSubmission", back_populates="audits")
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="submission_audits")
