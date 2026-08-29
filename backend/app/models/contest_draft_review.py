import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base


class ContestDraftReviewAudit(Base):
    __tablename__ = "contest_draft_review_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("contest_drafts.id", ondelete="CASCADE"), index=True)
    dispute_id: Mapped[str] = mapped_column(String(64), ForeignKey("disputes.id", ondelete="CASCADE"), index=True)

    previous_review_status: Mapped[str] = mapped_column(String(32))
    new_review_status: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(32))  # APPROVE, REJECT
    reviewer_reference: Mapped[str] = mapped_column(String(100), default="merchant_admin")
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    input_fingerprint: Mapped[str] = mapped_column(String(64))
    generator_version: Mapped[str] = mapped_column(String(64), default="contest-draft-v1.0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
