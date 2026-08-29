"""
Dashboard Schemas — Chargeback Shield Task 6.1

Defines strict Pydantic schemas for operational monitoring, aggregate summary metrics,
filtered dispute lists, detailed dispute observability views, operational alerts, and timeline events.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """Aggregated operational metrics across local Chargeback Shield records."""
    total_disputes: int = 0
    evidence_uploaded: int = 0
    evidence_processing: int = 0
    evidence_ready: int = 0
    extraction_completed: int = 0
    matching_completed: int = 0
    eligible_count: int = 0
    human_review_count: int = 0
    not_eligible_count: int = 0
    drafts_pending_review: int = 0
    drafts_approved: int = 0
    drafts_rejected: int = 0
    preflight_ready: int = 0
    preflight_blocked: int = 0
    submissions_in_progress: int = 0
    submissions_submitted: int = 0
    submissions_unknown: int = 0
    reconciliation_required: int = 0
    under_review_count: int = 0
    action_required_count: int = 0
    won_count: int = 0
    lost_count: int = 0
    failed_operations: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class DisputeDashboardItem(BaseModel):
    """Lightweight dispute summary item for paginated list view."""
    dispute_id: str
    payment_id: str
    amount: int
    currency: str
    dispute_status: str
    policy_outcome: Optional[str] = None
    review_status: Optional[str] = None
    preflight_status: Optional[str] = None
    submission_status: Optional[str] = None
    lifecycle_status: Optional[str] = None
    outcome: Optional[str] = None
    created_at: datetime


class DisputeListResponse(BaseModel):
    """Paginated dispute list response."""
    items: List[DisputeDashboardItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class OperationalAlert(BaseModel):
    """Informational operational alert raised by deterministic monitoring rules."""
    alert_code: str
    severity: str  # INFO, WARNING, CRITICAL
    message: str
    dispute_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TimelineEvent(BaseModel):
    """Chronological lifecycle event entry."""
    timestamp: datetime
    stage: str
    event_type: str
    description: str
    source_record: str


class DisputeDashboardDetail(BaseModel):
    """Unified 360-degree observability view for a single dispute."""
    dispute: Dict[str, Any]
    evidence: Dict[str, Any]
    matching: Dict[str, Any]
    policy: Dict[str, Any]
    contest_draft: Dict[str, Any]
    preflight: Dict[str, Any]
    submission: Dict[str, Any]
    razorpay_lifecycle: Dict[str, Any]
    timeline: List[TimelineEvent]
    alerts: List[OperationalAlert]


class ReconciliationRequiredItem(BaseModel):
    """Dispute record requiring status reconciliation."""
    dispute_id: str
    submission_id: str
    submitted_at: Optional[datetime] = None
    current_submission_status: str
    last_reconciliation_at: Optional[datetime] = None
    last_known_razorpay_status: Optional[str] = None
    failure_reason: Optional[str] = None


class ActionRequiredItem(BaseModel):
    """Dispute record requiring merchant action on Razorpay."""
    dispute_id: str
    payment_id: str
    amount: int
    currency: str
    razorpay_status: str
    razorpay_phase: Optional[str] = None
    respond_by: Optional[datetime] = None
    policy_outcome: Optional[str] = None
    review_status: Optional[str] = None
    observed_at: datetime


class OutcomeSummary(BaseModel):
    """Summary metrics of dispute outcomes."""
    won_count: int = 0
    lost_count: int = 0
    under_review_count: int = 0
    pending_count: int = 0
    unknown_count: int = 0
    total_count: int = 0
