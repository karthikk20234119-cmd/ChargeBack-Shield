import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base


class ContestDraft(Base):
    __tablename__ = "contest_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id: Mapped[str] = mapped_column(String(64), ForeignKey("disputes.id", ondelete="CASCADE"), index=True)
    policy_result_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("policy_results.id", ondelete="SET NULL"), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(32), index=True)  # DRAFT, REVIEW_REQUIRED, BLOCKED
    review_status: Mapped[str] = mapped_column(String(32), default="PENDING_REVIEW", index=True)  # PENDING_REVIEW, APPROVED, REJECTED
    draft_version: Mapped[str] = mapped_column(String(32), default="1.0")
    generator_version: Mapped[str] = mapped_column(String(64), default="contest-draft-v1.0.0")

    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    dispute_context: Mapped[dict] = mapped_column(JSON, default=dict)
    factual_arguments: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_references: Mapped[dict] = mapped_column(JSON, default=dict)
    limitations: Mapped[dict] = mapped_column(JSON, default=dict)
    review_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    input_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="contest_drafts")
