"""
Contest Submission Schemas — Chargeback Shield Task 5.4B

Defines strict Pydantic schemas for local submission state, submission client requests/responses,
API contracts, and sanitized audit schemas.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SubmissionStatus(str, Enum):
    PRECHECK_REQUIRED = "PRECHECK_REQUIRED"
    READY = "READY"
    SUBMISSION_AUTHORIZED = "SUBMISSION_AUTHORIZED"
    SUBMISSION_IN_PROGRESS = "SUBMISSION_IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class FailureCategory(str, Enum):
    NONE = "NONE"
    CLIENT_ERROR_4XX = "CLIENT_ERROR_4XX"
    AUTH_ERROR_401_403 = "AUTH_ERROR_401_403"
    NOT_FOUND_404 = "NOT_FOUND_404"
    CONFLICT_409 = "CONFLICT_409"
    RATE_LIMIT_429 = "RATE_LIMIT_429"
    SERVER_ERROR_5XX = "SERVER_ERROR_5XX"
    TIMEOUT_AMBIGUOUS = "TIMEOUT_AMBIGUOUS"
    CONNECTION_FAILURE = "CONNECTION_FAILURE"
    VAL_ERROR = "VAL_ERROR"


class RazorpayContestSubmissionRequest(BaseModel):
    """Internal request payload prepared for Razorpay contest API."""
    dispute_id: str
    amount_minor: int
    currency: str
    summary: str
    comments: Optional[str] = None
    documents: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)


class RazorpayContestSubmissionResponse(BaseModel):
    """Raw response received from external Razorpay API call."""
    dispute_id: str
    razorpay_status: str
    razorpay_reference_id: Optional[str] = None
    http_status_code: int
    submitted_at: datetime
    raw_response: Dict[str, Any] = Field(default_factory=dict)


class ContestSubmissionApiRequest(BaseModel):
    """
    Empty client body schema for POST /api/disputes/{dispute_id}/contest-submission.
    Forbids extra input fields to prevent payload injection attacks.
    """
    model_config = ConfigDict(extra="forbid")


class ContestSubmissionResponse(BaseModel):
    """Public API response returned to client after contest submission execution."""
    id: str
    dispute_id: str
    contest_draft_id: str
    preflight_id: str
    status: SubmissionStatus
    razorpay_status: Optional[str] = None
    razorpay_reference_id: Optional[str] = None
    idempotency_key: str
    submitted_at: Optional[datetime] = None
    failure_category: FailureCategory = FailureCategory.NONE
    failure_reason: Optional[str] = None
    audit_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
