"""
MatchResult Database Model — Phase 4 Task 4.2

Stores deterministic evidence match results with dispute/evidence foreign keys,
provenance metadata, normalized values, confidence, and explanations.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dispute_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("disputes.id", ondelete="CASCADE"), index=True
    )
    evidence_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("evidence_documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    processed_artifact_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("processed_artifacts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    fact_name: Mapped[str] = mapped_column(String(64), index=True)  # e.g. amount_minor, payment_id
    field: Mapped[str] = mapped_column(String(64), index=True, default="fact")  # Backwards compatibility alias

    expected_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    observed_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Backwards compatibility alias

    normalized_expected_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_expected: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    normalized_observed_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_extracted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(32), index=True)  # MATCH, MISMATCH, MISSING, AMBIGUOUS, etc.
    confidence: Mapped[str] = mapped_column(String(16), default="MEDIUM")  # HIGH, MEDIUM, LOW

    source_page: Mapped[int] = mapped_column(Integer, default=1)
    source_region: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(32), default="ocr")
    matcher_version: Mapped[str] = mapped_column(String(16), default="1.0")

    explanation: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, default="")  # Backwards compatibility alias

    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(64), default="general")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="match_results")
    evidence: Mapped[Optional["EvidenceDocument"]] = relationship("EvidenceDocument")
