"""
Contest Submission Reconciliation Schemas — Chargeback Shield Task 5.4C

Defines strict Pydantic schemas for reconciliation outcome states, API request/response models,
and audit record schemas.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict

from backend.app.schemas.contest_submission import SubmissionStatus, FailureCategory


class ReconciliationOutcome(str, Enum):
    RECONCILED_SUBMITTED = "RECONCILED_SUBMITTED"
    RECONCILED_FAILED = "RECONCILED_FAILED"
    UNRESOLVED_UNKNOWN = "UNRESOLVED_UNKNOWN"
    ALREADY_SUBMITTED = "ALREADY_SUBMITTED"
    STALE_FINGERPRINT = "STALE_FINGERPRINT"
    ERROR_LOOKUP_FAILED = "ERROR_LOOKUP_FAILED"


class ContestSubmissionReconcileApiRequest(BaseModel):
    """
    Empty client body schema for POST /api/disputes/{dispute_id}/contest-submission/reconcile.
    Forbids extra input fields to prevent payload injection attacks.
    """
    model_config = ConfigDict(extra="forbid")


class ContestSubmissionReconciliationResponse(BaseModel):
    """Public API response returned to client after contest submission status reconciliation."""
    submission_id: str
    dispute_id: str
    previous_status: SubmissionStatus
    new_status: SubmissionStatus
    outcome: ReconciliationOutcome
    razorpay_status: Optional[str] = None
    razorpay_reference_id: Optional[str] = None
    reconciled_at: datetime
    reconciliation_reason: str
    audit_id: Optional[str] = None
