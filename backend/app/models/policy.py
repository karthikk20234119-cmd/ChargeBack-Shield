import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base


class PolicyResult(Base):
    __tablename__ = "policy_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id: Mapped[str] = mapped_column(String(64), ForeignKey("disputes.id", ondelete="CASCADE"), index=True)

    policy_version: Mapped[str] = mapped_column(String(32), default="cb13.1-v1.0")
    outcome: Mapped[str] = mapped_column(String(32), index=True)  # ELIGIBLE, NOT_ELIGIBLE, HUMAN_REVIEW
    decision: Mapped[str] = mapped_column(String(32), default="HUMAN_REVIEW")
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)

    summary: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    critical_findings: Mapped[dict] = mapped_column(JSON, default=dict)
    reason_codes: Mapped[dict] = mapped_column(JSON, default=dict)
    rule_results: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    financial_safety_verified: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="policy_results")
