"""
Contest Submission Preflight Schemas — Chargeback Shield Task 5.3

Provides typed Pydantic models for the deterministic local preflight authorization gate.
LOCAL ONLY. ZERO Razorpay mutation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PreflightStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    INVALID = "INVALID"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class CheckSeverity(str, Enum):
    BLOCKING = "BLOCKING"
    WARNING = "WARNING"
    INFO = "INFO"


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    INFO = "INFO"


class PreflightCheck(BaseModel):
    check_code: str = Field(..., description="Deterministic code for preflight check")
    status: CheckStatus = Field(..., description="Outcome of check: PASS, FAIL, WARN, INFO")
    message: str = Field(..., description="Human-readable explanation of check result")
    severity: CheckSeverity = Field(..., description="Severity level: BLOCKING, WARNING, INFO")
    source_ids: List[str] = Field(default_factory=list, description="IDs of source records linked to check")


class ContestSubmissionPreflightResult(BaseModel):
    id: str = Field(..., description="Unique UUID for preflight verification record")
    dispute_id: str = Field(..., description="Target dispute identifier")
    contest_draft_id: str = Field(..., description="ID of evaluated contest draft")
    policy_result_id: Optional[str] = Field(None, description="ID of evaluated policy result")
    status: PreflightStatus = Field(..., description="Overall preflight decision status")
    draft_status: str = Field(..., description="Policy status on draft: DRAFT, REVIEW_REQUIRED, BLOCKED")
    review_status: str = Field(..., description="Human review status: PENDING_REVIEW, APPROVED, REJECTED")
    input_fingerprint: Optional[str] = Field(None, description="SHA-256 canonical input fingerprint")
    draft_version: str = Field("1.0", description="Draft version string")
    generator_version: str = Field("contest-draft-v1.0.0", description="Draft generator version string")
    checks: List[PreflightCheck] = Field(default_factory=list, description="List of performed preflight checks")
    blocking_reasons: List[str] = Field(default_factory=list, description="List of blocking reasons if status is BLOCKED/INVALID/REVIEW_REQUIRED")
    warnings: List[str] = Field(default_factory=list, description="List of non-blocking warning messages")
    verified_financial_identity: Dict[str, Any] = Field(default_factory=dict, description="Verified payment_id, amount, currency")
    verified_evidence_count: int = Field(0, description="Number of verified evidence documents linked")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of preflight run")
