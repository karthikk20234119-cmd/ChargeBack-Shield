"""
Contest Submission Preflight Database Model — Chargeback Shield Task 5.3

Stores immutable snapshots of local preflight authorization verification records.
LOCAL ONLY. ZERO Razorpay mutation operations.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base


class ContestSubmissionPreflight(Base):
    __tablename__ = "contest_submission_preflights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id: Mapped[str] = mapped_column(String(64), ForeignKey("disputes.id", ondelete="CASCADE"), index=True)
    contest_draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("contest_drafts.id", ondelete="CASCADE"), index=True)
    policy_result_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("policy_results.id", ondelete="SET NULL"), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(32), index=True)  # READY, BLOCKED, STALE, INVALID, REVIEW_REQUIRED
    draft_status: Mapped[str] = mapped_column(String(32))
    review_status: Mapped[str] = mapped_column(String(32))
    input_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    draft_version: Mapped[str] = mapped_column(String(32), default="1.0")
    generator_version: Mapped[str] = mapped_column(String(64), default="contest-draft-v1.0.0")

    checks: Mapped[list] = mapped_column(JSON, default=list)
    blocking_reasons: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    verified_financial_identity: Mapped[dict] = mapped_column(JSON, default=dict)
    verified_evidence_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="preflights")
    contest_draft: Mapped["ContestDraft"] = relationship("ContestDraft")
