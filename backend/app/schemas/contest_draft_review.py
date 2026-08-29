"""
Contest Draft Review Schemas — Chargeback Shield Task 5.2

Defines strict Pydantic models for human-review request and response contracts.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from backend.app.schemas.contest_draft import ReviewStatus


class ReviewDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ContestDraftReviewRequest(BaseModel):
    decision: ReviewDecision
    comment: Optional[str] = Field(default=None, max_length=2000, description="Optional reviewer feedback capped at 2000 characters.")
    reviewer_reference: Optional[str] = Field(default="merchant_admin", max_length=100, description="Reviewer identification reference.")


class ContestDraftReviewResponse(BaseModel):
    audit_id: str
    draft_id: str
    dispute_id: str
    previous_review_status: ReviewStatus
    new_review_status: ReviewStatus
    decision: ReviewDecision
    reviewer_reference: str
    comment: Optional[str] = None
    input_fingerprint: str
    timestamp: datetime
