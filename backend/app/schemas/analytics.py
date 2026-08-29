"""
Analytics, Management Reporting & Performance Insights Pydantic Schemas — Chargeback Shield Task 6.4

Provides typed DTO schemas for management summaries, outcome analytics, evidence processing metrics,
matching evaluations, policy reviews, draft approvals, contest submission performance, operational SLA metrics,
12-stage lifecycle funnels, bottleneck analyses, failure breakdowns, security/compliance findings,
financial integrity checks, and canonical report exports.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TimeRangeEnum(str, Enum):
    TODAY = "TODAY"
    LAST_7_DAYS = "LAST_7_DAYS"
    LAST_30_DAYS = "LAST_30_DAYS"
    LAST_90_DAYS = "LAST_90_DAYS"
    THIS_YEAR = "THIS_YEAR"
    CUSTOM = "CUSTOM"


class DisputeOutcomeAnalytics(BaseModel):
    total_disputes: int = 0
    pending: int = 0
    under_review: int = 0
    action_required: int = 0
    won: int = 0
    lost: int = 0
    unknown: int = 0
    win_rate: float = 0.0
    loss_rate: float = 0.0


class EvidenceAnalytics(BaseModel):
    total_documents: int = 0
    processed_documents: int = 0
    failed_documents: int = 0
    rejected_documents: int = 0
    average_documents_per_dispute: float = 0.0
    evidence_completeness_rate: float = 0.0
    documents_by_type: Dict[str, int] = Field(default_factory=dict)
    documents_by_status: Dict[str, int] = Field(default_factory=dict)
    processing_success_rate: float = 0.0
    rejection_rate: float = 0.0


class MatchingAnalytics(BaseModel):
    total_matches: int = 0
    matches: int = 0
    mismatches: int = 0
    missing: int = 0
    ambiguous: int = 0
    conflicts: int = 0
    unverifiable: int = 0
    not_comparable: int = 0
    match_success_rate: float = 0.0
    mismatch_rate: float = 0.0
    conflict_rate: float = 0.0


class PolicyAnalytics(BaseModel):
    total_policy_evaluations: int = 0
    eligible: int = 0
    human_review: int = 0
    not_eligible: int = 0
    policy_failure_rate: float = 0.0
    rule_failure_distribution: Dict[str, int] = Field(default_factory=dict)
    review_rate: float = 0.0
    eligibility_rate: float = 0.0


class DraftAnalytics(BaseModel):
    total_drafts: int = 0
    draft: int = 0
    review_required: int = 0
    blocked: int = 0
    pending_review: int = 0
    approved: int = 0
    rejected: int = 0
    approval_rate: float = 0.0
    rejection_rate: float = 0.0
    review_pending_rate: float = 0.0


class SubmissionAnalytics(BaseModel):
    total_submissions: int = 0
    submitted: int = 0
    failed: int = 0
    unknown: int = 0
    submission_success_rate: float = 0.0
    unknown_rate: float = 0.0
    failure_distribution: Dict[str, int] = Field(default_factory=dict)
    reconciliation_rate: float = 0.0


class OperationalAnalytics(BaseModel):
    total_alerts: int = 0
    open_alerts: int = 0
    critical_alerts: int = 0
    high_alerts: int = 0
    medium_alerts: int = 0
    overdue_alerts: int = 0
    security_alerts: int = 0
    compliance_alerts: int = 0
    reconciliation_required: int = 0
    alerts_by_category: Dict[str, int] = Field(default_factory=dict)
    alerts_by_code: Dict[str, int] = Field(default_factory=dict)


class LifecycleTimingAnalytics(BaseModel):
    average_processing_hours: float = 0.0
    average_review_hours: float = 0.0
    average_preflight_hours: float = 0.0
    average_submission_resolution_hours: float = 0.0
    average_total_lifecycle_hours: float = 0.0


class ManagementAnalyticsSummary(BaseModel):
    total_disputes: int = 0
    active_disputes: int = 0
    won: int = 0
    lost: int = 0
    pending: int = 0
    win_rate: float = 0.0
    total_evidence_documents: int = 0
    policy_review_rate: float = 0.0
    draft_approval_rate: float = 0.0
    submission_success_rate: float = 0.0
    unknown_submission_count: int = 0
    critical_alert_count: int = 0
    reconciliation_required_count: int = 0


class OutcomePeriodItem(BaseModel):
    period_label: str
    won: int = 0
    lost: int = 0
    pending: int = 0
    total: int = 0


class OutcomeAnalyticsReport(BaseModel):
    total: int = 0
    won: int = 0
    lost: int = 0
    pending: int = 0
    under_review: int = 0
    action_required: int = 0
    unknown: int = 0
    win_rate: float = 0.0
    loss_rate: float = 0.0
    outcome_by_period: List[OutcomePeriodItem] = Field(default_factory=list)


class FunnelStageItem(BaseModel):
    stage: str
    count: int = 0
    conversion_rate: float = 0.0
    drop_off_count: int = 0


class LifecycleFunnelReport(BaseModel):
    stages: List[FunnelStageItem] = Field(default_factory=list)
    total_started: int = 0
    total_completed: int = 0
    overall_conversion_rate: float = 0.0


class BottleneckItem(BaseModel):
    stage: str
    metric: str
    value: float = 0.0
    severity: str = "INFO"  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    explanation: str


class BottleneckAnalysisReport(BaseModel):
    bottlenecks: List[BottleneckItem] = Field(default_factory=list)
    primary_bottleneck_stage: str = "NONE"


class FailureAnalyticsReport(BaseModel):
    evidence_failures: int = 0
    extraction_failures: int = 0
    matching_conflicts: int = 0
    policy_failures: int = 0
    draft_failures: int = 0
    preflight_failures: int = 0
    submission_failures: int = 0
    reconciliation_failures: int = 0
    lifecycle_failures: int = 0
    security_failures: int = 0
    failure_rates_by_stage: Dict[str, float] = Field(default_factory=dict)


class SecurityComplianceAnalyticsReport(BaseModel):
    prompt_injection_findings: int = 0
    path_traversal_attempts: int = 0
    mime_violations: int = 0
    magic_byte_failures: int = 0
    hash_mismatches: int = 0
    stale_fingerprint_events: int = 0
    credential_security_findings: int = 0
    audit_integrity_exceptions: int = 0
    provenance_failures: int = 0


class FinancialIntegrityAnalyticsReport(BaseModel):
    disputes_checked: int = 0
    verified: int = 0
    violations: int = 0
    violation_rate: float = 0.0
    affected_disputes: List[str] = Field(default_factory=list)


class AnalyticsExport(BaseModel):
    report_version: str = "1.0.0"
    generated_at: datetime
    date_range: Dict[str, Any] = Field(default_factory=dict)
    summary: ManagementAnalyticsSummary
    outcomes: OutcomeAnalyticsReport
    evidence: EvidenceAnalytics
    matching: MatchingAnalytics
    policy: PolicyAnalytics
    drafts: DraftAnalytics
    submissions: SubmissionAnalytics
    operations: OperationalAnalytics
    sla: Dict[str, Any] = Field(default_factory=dict)
    funnel: LifecycleFunnelReport
    bottlenecks: BottleneckAnalysisReport
    failures: FailureAnalyticsReport
    security: SecurityComplianceAnalyticsReport
    financial_integrity: FinancialIntegrityAnalyticsReport
    report_hash: str
