"""
SLA Policy & Calculation Service — Chargeback Shield Task 6.3

Provides deterministic, timezone-aware SLA calculations for human reviews, submissions,
reconciliations, action-required gateway states, and evidence processing.

CONFIGURABLE CONSTANTS (SERVER-SIDE):
- HUMAN_REVIEW_SLA_HOURS = 24.0
- ACTION_REQUIRED_SLA_HOURS = 12.0
- UNKNOWN_SUBMISSION_SLA_HOURS = 6.0
- RECONCILIATION_SLA_HOURS = 12.0
- EVIDENCE_PROCESSING_SLA_HOURS = 4.0
- WARNING_THRESHOLD_PERCENT = 0.75
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from backend.app.schemas.operational_alert import AlertSeverity

# Mandatory SLA Constants
HUMAN_REVIEW_SLA_HOURS = 24.0
ACTION_REQUIRED_SLA_HOURS = 12.0
UNKNOWN_SUBMISSION_SLA_HOURS = 6.0
RECONCILIATION_SLA_HOURS = 12.0
EVIDENCE_PROCESSING_SLA_HOURS = 4.0
WARNING_THRESHOLD_PERCENT = 0.75

SLA_MAP = {
    "HUMAN_REVIEW_REQUIRED": HUMAN_REVIEW_SLA_HOURS,
    "BLOCKED_DRAFT": HUMAN_REVIEW_SLA_HOURS,
    "SUBMISSION_STUCK": UNKNOWN_SUBMISSION_SLA_HOURS,
    "SUBMISSION_UNKNOWN": UNKNOWN_SUBMISSION_SLA_HOURS,
    "SUBMISSION_FAILED": UNKNOWN_SUBMISSION_SLA_HOURS,
    "RECONCILIATION_REQUIRED": RECONCILIATION_SLA_HOURS,
    "RECONCILIATION_OVERDUE": RECONCILIATION_SLA_HOURS,
    "ACTION_REQUIRED": ACTION_REQUIRED_SLA_HOURS,
    "EVIDENCE_PROCESSING_FAILED": EVIDENCE_PROCESSING_SLA_HOURS,
}


def calculate_due_at(detected_at: datetime, sla_hours: float) -> datetime:
    """Calculates the due_at deadline timestamp given a start timestamp and SLA duration."""
    return detected_at + timedelta(hours=sla_hours)


def calculate_sla_metrics(
    detected_at: datetime,
    due_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> Tuple[float, float, str, AlertSeverity]:
    """
    Calculates SLA status, elapsed hours, remaining hours, and derived severity.

    Returns:
        (elapsed_hours, remaining_hours, sla_status, derived_severity)
    """
    if now is None:
        now = datetime.utcnow()

    # Ensure naive datetime comparisons
    if detected_at.tzinfo is not None:
        detected_at = detected_at.astimezone(timezone.utc).replace(tzinfo=None)
    if due_at and due_at.tzinfo is not None:
        due_at = due_at.astimezone(timezone.utc).replace(tzinfo=None)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)

    elapsed_seconds = (now - detected_at).total_seconds()
    elapsed_hours = round(max(0.0, elapsed_seconds / 3600.0), 2)

    if not due_at:
        return elapsed_hours, 0.0, "ON_TIME", AlertSeverity.INFO

    total_sla_seconds = (due_at - detected_at).total_seconds()
    remaining_seconds = (due_at - now).total_seconds()
    remaining_hours = round(remaining_seconds / 3600.0, 2)

    if remaining_seconds < 0:
        # Overdue
        if abs(remaining_seconds) >= total_sla_seconds:
            return elapsed_hours, remaining_hours, "CRITICAL_OVERDUE", AlertSeverity.CRITICAL
        return elapsed_hours, remaining_hours, "OVERDUE", AlertSeverity.HIGH

    if total_sla_seconds > 0 and (elapsed_seconds / total_sla_seconds) >= WARNING_THRESHOLD_PERCENT:
        return elapsed_hours, remaining_hours, "WARNING", AlertSeverity.MEDIUM

    return elapsed_hours, remaining_hours, "ON_TIME", AlertSeverity.INFO
