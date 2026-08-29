"""
Contest Draft Schemas — Chargeback Shield Task 5.1

Defines strict Pydantic models for human-reviewable contest response drafts.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ContestDraftStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class FactualArgument(BaseModel):
    argument_id: str
    heading: str
    statement: str
    support_level: str = "VERIFIED"  # VERIFIED, UNVERIFIED, CONTRADICTED
    source_match_result_ids: List[str] = Field(default_factory=list)
    source_evidence_ids: List[str] = Field(default_factory=list)
    source_fact_names: List[str] = Field(default_factory=list)
    explanation: str = ""


class EvidenceReference(BaseModel):
    evidence_id: str
    evidence_type: str
    document_name: str
    source_page: int = 1
    description: str = ""


class ReviewFlag(BaseModel):
    flag_code: str
    severity: str = "MEDIUM"  # CRITICAL, HIGH, MEDIUM, LOW
    message: str
    source_ids: List[str] = Field(default_factory=list)


class ContestDraft(BaseModel):
    id: Optional[str] = None
    dispute_id: str
    policy_result_id: Optional[str] = None
    draft_version: str = "1.0"
    generator_version: str = "contest-draft-v1.0.0"
    status: ContestDraftStatus
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    title: str
    summary: str
    dispute_context: Dict[str, Any] = Field(default_factory=dict)
    factual_arguments: List[FactualArgument] = Field(default_factory=list)
    evidence_references: List[EvidenceReference] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    review_flags: List[ReviewFlag] = Field(default_factory=list)
    input_fingerprint: Optional[str] = None
    generated_at: Optional[datetime] = None
