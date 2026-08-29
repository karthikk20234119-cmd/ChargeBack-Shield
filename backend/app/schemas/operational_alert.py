"""
Operational Alert & SLA Monitoring Pydantic Schemas — Chargeback Shield Task 6.3

Provides typed schemas for operational alerts, SLA tracking, exception management, health reporting,
and alert detection responses.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class AlertCategory(str, Enum):
    SLA = "SLA"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    SUBMISSION = "SUBMISSION"
    RECONCILIATION = "RECONCILIATION"
    LIFECYCLE = "LIFECYCLE"
    EVIDENCE = "EVIDENCE"
    PROCESSING = "PROCESSING"
    POLICY = "POLICY"
    SECURITY = "SECURITY"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    COMPLIANCE = "COMPLIANCE"
    SYSTEM = "SYSTEM"


class OperationalAlert(BaseModel):
    alert_id: str
    dispute_id: str
    category: AlertCategory
    code: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.OPEN
    title: str
    message: str
    source_type: str
    source_id: str
    created_at: datetime
    detected_at: datetime
    due_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    fingerprint: str

    model_config = ConfigDict(from_attributes=True)


class OperationalAlertSummary(BaseModel):
    total_open: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    human_review_count: int = 0
    submission_count: int = 0
    reconciliation_count: int = 0
    lifecycle_count: int = 0
    evidence_count: int = 0
    security_count: int = 0
    compliance_count: int = 0
    overdue_count: int = 0


class DisputeAlertDetail(BaseModel):
    dispute_id: str
    current_alerts: List[OperationalAlert] = Field(default_factory=list)
    alert_history: List[OperationalAlert] = Field(default_factory=list)
    unresolved_alerts: List[OperationalAlert] = Field(default_factory=list)
    resolved_alerts: List[OperationalAlert] = Field(default_factory=list)
    severity_summary: Dict[str, int] = Field(default_factory=dict)


class SLAItem(BaseModel):
    dispute_id: str
    alert_code: str
    detected_at: datetime
    due_at: Optional[datetime] = None
    elapsed_hours: float = 0.0
    remaining_hours: float = 0.0
    sla_status: str = "ON_TIME"  # ON_TIME, WARNING, OVERDUE, CRITICAL_OVERDUE


class SLAMonitoringReport(BaseModel):
    total_tracked: int = 0
    on_time: int = 0
    approaching_deadline: int = 0
    overdue: int = 0
    critical_overdue: int = 0
    average_elapsed_hours: float = 0.0
    by_category: Dict[str, int] = Field(default_factory=dict)
    items: List[SLAItem] = Field(default_factory=list)


class OperationalExceptionReport(BaseModel):
    critical_exceptions: List[OperationalAlert] = Field(default_factory=list)
    high_exceptions: List[OperationalAlert] = Field(default_factory=list)
    unresolved_exceptions: List[OperationalAlert] = Field(default_factory=list)
    stale_items: List[OperationalAlert] = Field(default_factory=list)
    security_exceptions: List[OperationalAlert] = Field(default_factory=list)
    financial_exceptions: List[OperationalAlert] = Field(default_factory=list)
    compliance_exceptions: List[OperationalAlert] = Field(default_factory=list)


class OperationalHealthReport(BaseModel):
    total_disputes: int = 0
    active_disputes: int = 0
    pending_reviews: int = 0
    blocked_drafts: int = 0
    unknown_submissions: int = 0
    reconciliation_required: int = 0
    action_required: int = 0
    stale_items: int = 0
    evidence_failures: int = 0
    policy_failures: int = 0
    critical_alerts: int = 0
    high_alerts: int = 0
    final_outcomes: Dict[str, int] = Field(default_factory=dict)


class AlertDetectionRequest(BaseModel):
    """Empty body request for alert detection endpoint."""

    model_config = ConfigDict(extra="forbid")


class AlertDetectionResult(BaseModel):
    detected_count: int = 0
    new_count: int = 0
    existing_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    alerts: List[OperationalAlert] = Field(default_factory=list)
