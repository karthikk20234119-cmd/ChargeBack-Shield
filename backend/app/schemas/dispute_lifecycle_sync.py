"""
Dispute Lifecycle Synchronization Schemas — Chargeback Shield Task 5.5

Defines strict Pydantic schemas for lifecycle status enums, dispute outcome enums,
sync result types, empty API request models, and response models.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DisputeLifecycleStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    WON = "WON"
    LOST = "LOST"
    UNKNOWN_EXTERNAL_STATUS = "UNKNOWN_EXTERNAL_STATUS"


class DisputeOutcome(str, Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    WON = "WON"
    LOST = "LOST"
    UNKNOWN = "UNKNOWN"


class SyncResultType(str, Enum):
    STATE_CHANGED = "STATE_CHANGED"
    UNCHANGED = "UNCHANGED"
    TERMINAL_REACHED = "TERMINAL_REACHED"
    UNEXPECTED_TRANSITION = "UNEXPECTED_TRANSITION"
    STALE_LOCAL_STATE = "STALE_LOCAL_STATE"
    SYNC_FAILED = "SYNC_FAILED"


class DisputeLifecycleSyncApiRequest(BaseModel):
    """
    Empty client request body schema for POST /api/disputes/{dispute_id}/lifecycle/sync.
    Forbids extra input fields to prevent payload injection attacks.
    """
    model_config = ConfigDict(extra="forbid")


class DisputeLifecycleSyncResponse(BaseModel):
    """Public API response returned to client after dispute lifecycle synchronization."""
    dispute_id: str
    razorpay_dispute_id: str
    previous_status: DisputeLifecycleStatus
    current_status: DisputeLifecycleStatus
    razorpay_status: Optional[str] = None
    razorpay_phase: Optional[str] = None
    outcome: DisputeOutcome
    transition_type: str
    synchronization_result: SyncResultType
    snapshot_id: Optional[str] = None
    audit_id: Optional[str] = None
    observed_at: datetime
