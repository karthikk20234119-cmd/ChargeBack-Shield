"""
Operational Alert, SLA Monitoring & Exception Management Service — Chargeback Shield Task 6.3

Transforms existing dispute, evidence, processing, extraction, matching, policy, draft, review,
preflight, submission, reconciliation, and lifecycle records into actionable operational alerts.

CRITICAL INVARIANTS:
- STRICTLY READ-ONLY AGAINST BUSINESS ENTITIES: Consumes local DB records exclusively.
- ZERO RAZORPAY NETWORK CALLS: Does NOT import Razorpay client classes or make external HTTP calls.
- ZERO SOURCE MUTATIONS: Never mutates disputes, documents, artifacts, policy results, drafts, preflights, submissions, or snapshots.
- ONLY PERMITTED MUTATION: Creating/updating records in the `operational_alerts` table.
- DETERMINISTIC DEDUPLICATION: Computes SHA-256 alert fingerprints to suppress duplicate alert generation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from enum import Enum
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Set

from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.contest_draft import ContestDraft
from backend.app.models.contest_draft_review import ContestDraftReviewAudit
from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.contest_submission_audit import ContestSubmissionAudit
from backend.app.models.contest_submission_preflight import ContestSubmissionPreflight
from backend.app.models.dispute import Dispute
from backend.app.models.dispute_lifecycle_snapshot import DisputeLifecycleSnapshot
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.matching import MatchResult
from backend.app.models.operational_alert import OperationalAlert as OperationalAlertModel
from backend.app.models.policy import PolicyResult
from backend.app.models.processed_artifact import ProcessedArtifact
from backend.app.schemas.operational_alert import (
    AlertCategory,
    AlertDetectionResult,
    AlertSeverity,
    AlertStatus,
    DisputeAlertDetail,
    OperationalAlert,
    OperationalAlertSummary,
    OperationalExceptionReport,
    OperationalHealthReport,
    SLAItem,
    SLAMonitoringReport,
)
from backend.app.services.sla_policy import (
    SLA_MAP,
    calculate_due_at,
    calculate_sla_metrics,
)

logger = logging.getLogger(__name__)

SEVERITY_PRIORITY = {
    "CRITICAL": 1,
    "HIGH": 2,
    "MEDIUM": 3,
    "LOW": 4,
    "INFO": 5,
}


class OperationalAlertException(Exception):
    """Raised when operational alert operations fail or alert is not found."""

    def __init__(self, message: str, status_code: int = 404):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def compute_alert_fingerprint(
    dispute_id: str,
    code: str,
    source_type: str,
    source_id: str,
    state: str,
    bucket_hours: int = 1,
) -> str:
    """Computes a deterministic SHA-256 fingerprint for alert deduplication."""
    now = datetime.utcnow()
    # Bucket timestamps to avoid microsecond jitter
    bucket = now.strftime(f"%Y-%m-%d-%H")
    raw = f"{dispute_id}|{code}|{source_type}|{source_id}|{state}|{bucket}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sanitize_alert_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Scrubs sensitive credentials, tokens, and authorization headers from alert metadata."""
    if not isinstance(metadata, dict):
        return {}
    sanitized = {}
    forbidden_keys = {"auth", "key", "secret", "password", "token", "credential", "cookie", "authorization"}
    for k, v in metadata.items():
        if any(f in k.lower() for f in forbidden_keys):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_alert_metadata(v)
        else:
            sanitized[k] = v
    return sanitized


def _model_to_schema(a: OperationalAlertModel) -> OperationalAlert:
    """Converts OperationalAlertModel to OperationalAlert Pydantic schema safely."""
    return OperationalAlert(
        alert_id=a.id,
        dispute_id=a.dispute_id,
        category=a.category,
        code=a.code,
        severity=a.severity,
        status=a.status,
        title=a.title,
        message=a.message,
        source_type=a.source_type,
        source_id=a.source_id,
        created_at=a.created_at,
        detected_at=a.detected_at,
        due_at=a.due_at,
        resolved_at=a.resolved_at,
        metadata=a.extra_metadata or {},
        fingerprint=a.fingerprint,
    )


# ---------------------------------------------------------------------------
# Core Detection Engine
# ---------------------------------------------------------------------------


async def detect_operational_alerts(db: AsyncSession) -> AlertDetectionResult:
    """
    Scans all local dispute records and evaluates 24 mandatory detection rules.
    Creates or updates records in `operational_alerts` table.
    NEVER mutates source business entities.
    """
    db.expire_all()
    stmt = (
        select(Dispute)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Dispute.documents).selectinload(EvidenceDocument.extraction),
            selectinload(Dispute.documents).selectinload(EvidenceDocument.artifacts),
            selectinload(Dispute.match_results),
            selectinload(Dispute.policy_results),
            selectinload(Dispute.contest_drafts),
            selectinload(Dispute.preflights),
            selectinload(Dispute.submissions),
            selectinload(Dispute.submission_audits),
            selectinload(Dispute.lifecycle_snapshots),
        )
    )
    disputes = (await db.execute(stmt)).scalars().all()

    # Load existing OPEN / ACKNOWLEDGED alerts
    stmt_existing = select(OperationalAlertModel).where(OperationalAlertModel.status.in_(["OPEN", "ACKNOWLEDGED"]))
    existing_alerts_list = (await db.execute(stmt_existing)).scalars().all()
    existing_by_fp: Dict[str, OperationalAlertModel] = {a.fingerprint: a for a in existing_alerts_list}

    detected_fps: Set[str] = set()
    new_alert_models: List[OperationalAlertModel] = []
    existing_updated_count = 0
    critical_count = 0
    high_count = 0

    now = datetime.utcnow()

    for d in disputes:
        raw_dispute_alerts: List[Dict[str, Any]] = []

        # -------------------------------------------------------------------
        # Rule Category 1: HUMAN REVIEW
        # -------------------------------------------------------------------
        for draft in (d.contest_drafts or []):
            if draft.review_status == "PENDING_REVIEW":
                raw_dispute_alerts.append({
                    "category": AlertCategory.HUMAN_REVIEW,
                    "code": "HUMAN_REVIEW_REQUIRED",
                    "severity": AlertSeverity.MEDIUM,
                    "title": f"Human Review Pending for Dispute {d.id}",
                    "message": f"Contest draft {draft.id} is pending human review.",
                    "source_type": "contest_drafts",
                    "source_id": draft.id,
                    "state": "PENDING_REVIEW",
                    "detected_at": draft.created_at,
                    "metadata": {"draft_id": draft.id, "review_status": draft.review_status},
                })
            if draft.status == "REVIEW_REQUIRED":
                raw_dispute_alerts.append({
                    "category": AlertCategory.HUMAN_REVIEW,
                    "code": "HUMAN_REVIEW_REQUIRED",
                    "severity": AlertSeverity.MEDIUM,
                    "title": f"Review Required Draft for Dispute {d.id}",
                    "message": f"Contest draft {draft.id} status is REVIEW_REQUIRED.",
                    "source_type": "contest_drafts",
                    "source_id": draft.id,
                    "state": "REVIEW_REQUIRED",
                    "detected_at": draft.created_at,
                    "metadata": {"draft_id": draft.id, "status": draft.status},
                })
            if draft.status == "BLOCKED":
                raw_dispute_alerts.append({
                    "category": AlertCategory.HUMAN_REVIEW,
                    "code": "BLOCKED_DRAFT",
                    "severity": AlertSeverity.HIGH,
                    "title": f"Blocked Contest Draft for Dispute {d.id}",
                    "message": f"Contest draft {draft.id} is BLOCKED by policy/preflight.",
                    "source_type": "contest_drafts",
                    "source_id": draft.id,
                    "state": "BLOCKED",
                    "detected_at": draft.created_at,
                    "metadata": {"draft_id": draft.id, "status": draft.status},
                })

        # -------------------------------------------------------------------
        # Rule Category 2: SUBMISSION
        # -------------------------------------------------------------------
        for sub in (d.submissions or []):
            if sub.state == "SUBMISSION_IN_PROGRESS":
                is_stuck = (now - sub.created_at).total_seconds() > 900  # > 15 mins
                if is_stuck:
                    raw_dispute_alerts.append({
                        "category": AlertCategory.SUBMISSION,
                        "code": "SUBMISSION_STUCK",
                        "severity": AlertSeverity.HIGH,
                        "title": f"Submission Stuck for Dispute {d.id}",
                        "message": f"Submission {sub.id} in progress for over 15 minutes.",
                        "source_type": "contest_submissions",
                        "source_id": sub.id,
                        "state": "SUBMISSION_IN_PROGRESS",
                        "detected_at": sub.created_at,
                        "metadata": {"submission_id": sub.id, "state": sub.state},
                    })
            if sub.state == "UNKNOWN":
                raw_dispute_alerts.append({
                    "category": AlertCategory.SUBMISSION,
                    "code": "SUBMISSION_UNKNOWN",
                    "severity": AlertSeverity.CRITICAL,
                    "title": f"UNKNOWN Submission State for Dispute {d.id}",
                    "message": f"Submission {sub.id} is in UNKNOWN state and requires reconciliation.",
                    "source_type": "contest_submissions",
                    "source_id": sub.id,
                    "state": "UNKNOWN",
                    "detected_at": sub.created_at,
                    "metadata": {"submission_id": sub.id, "state": sub.state},
                })
            if sub.state == "FAILED":
                raw_dispute_alerts.append({
                    "category": AlertCategory.SUBMISSION,
                    "code": "SUBMISSION_FAILED",
                    "severity": AlertSeverity.MEDIUM,
                    "title": f"Submission Failed for Dispute {d.id}",
                    "message": f"Submission {sub.id} failed: {sub.failure_reason or 'No reason provided'}",
                    "source_type": "contest_submissions",
                    "source_id": sub.id,
                    "state": "FAILED",
                    "detected_at": sub.created_at,
                    "metadata": {"submission_id": sub.id, "failure_category": sub.failure_category},
                })

        # -------------------------------------------------------------------
        # Rule Category 3: RECONCILIATION
        # -------------------------------------------------------------------
        for sub in (d.submissions or []):
            if sub.state == "UNKNOWN":
                raw_dispute_alerts.append({
                    "category": AlertCategory.RECONCILIATION,
                    "code": "RECONCILIATION_REQUIRED",
                    "severity": AlertSeverity.HIGH,
                    "title": f"Reconciliation Required for Dispute {d.id}",
                    "message": f"Submission {sub.id} in UNKNOWN state requires gateway reconciliation.",
                    "source_type": "contest_submissions",
                    "source_id": sub.id,
                    "state": "UNKNOWN_RECONCILIATION",
                    "detected_at": sub.created_at,
                    "metadata": {"submission_id": sub.id},
                })
                if (now - sub.created_at).total_seconds() > 43200:  # > 12 hours
                    raw_dispute_alerts.append({
                        "category": AlertCategory.RECONCILIATION,
                        "code": "RECONCILIATION_OVERDUE",
                        "severity": AlertSeverity.HIGH,
                        "title": f"Reconciliation Overdue for Dispute {d.id}",
                        "message": f"Submission {sub.id} reconciliation overdue by > 12 hours.",
                        "source_type": "contest_submissions",
                        "source_id": sub.id,
                        "state": "RECONCILIATION_OVERDUE",
                        "detected_at": sub.created_at,
                        "metadata": {"submission_id": sub.id},
                    })

        # -------------------------------------------------------------------
        # Rule Category 4: LIFECYCLE
        # -------------------------------------------------------------------
        latest_snap = d.lifecycle_snapshots[0] if d.lifecycle_snapshots else None
        if (d.status or "").lower() == "action_required" or (latest_snap and (latest_snap.outcome or "").lower() == "action_required"):
            raw_dispute_alerts.append({
                "category": AlertCategory.LIFECYCLE,
                "code": "ACTION_REQUIRED",
                "severity": AlertSeverity.CRITICAL,
                "title": f"Action Required for Dispute {d.id}",
                "message": f"Dispute {d.id} is in ACTION_REQUIRED state requiring manual merchant action.",
                "source_type": "disputes",
                "source_id": d.id,
                "state": "ACTION_REQUIRED",
                "detected_at": d.updated_at or d.created_at,
                "metadata": {"dispute_id": d.id, "status": d.status},
            })

        for snap in (d.lifecycle_snapshots or []):
            if snap.razorpay_status == "unknown":
                raw_dispute_alerts.append({
                    "category": AlertCategory.LIFECYCLE,
                    "code": "UNKNOWN_EXTERNAL_STATUS",
                    "severity": AlertSeverity.HIGH,
                    "title": f"Unknown Gateway Status for Dispute {d.id}",
                    "message": f"Dispute lifecycle snapshot recorded unknown Razorpay status.",
                    "source_type": "dispute_lifecycle_snapshots",
                    "source_id": snap.id,
                    "state": "UNKNOWN_EXTERNAL",
                    "detected_at": snap.observed_at,
                    "metadata": {"snapshot_id": snap.id, "razorpay_status": snap.razorpay_status},
                })
            if snap.sync_result == "UNEXPECTED_TRANSITION":
                raw_dispute_alerts.append({
                    "category": AlertCategory.LIFECYCLE,
                    "code": "UNEXPECTED_LIFECYCLE_TRANSITION",
                    "severity": AlertSeverity.HIGH,
                    "title": f"Unexpected Lifecycle Transition for Dispute {d.id}",
                    "message": f"Lifecycle transition unexpected: {snap.previous_lifecycle_status} -> {snap.new_lifecycle_status}",
                    "source_type": "dispute_lifecycle_snapshots",
                    "source_id": snap.id,
                    "state": "UNEXPECTED_TRANSITION",
                    "detected_at": snap.observed_at,
                    "metadata": {"snapshot_id": snap.id, "sync_result": snap.sync_result},
                })

        # -------------------------------------------------------------------
        # Rule Category 5: EVIDENCE
        # -------------------------------------------------------------------
        docs = d.documents or []
        if not docs:
            raw_dispute_alerts.append({
                "category": AlertCategory.EVIDENCE,
                "code": "EVIDENCE_INCOMPLETE",
                "severity": AlertSeverity.MEDIUM,
                "title": f"No Evidence Uploaded for Dispute {d.id}",
                "message": f"Dispute {d.id} has zero evidence documents uploaded.",
                "source_type": "disputes",
                "source_id": d.id,
                "state": "NO_EVIDENCE",
                "detected_at": d.created_at,
                "metadata": {"dispute_id": d.id},
            })

        for doc in docs:
            if doc.processing_status == "FAILED":
                raw_dispute_alerts.append({
                    "category": AlertCategory.EVIDENCE,
                    "code": "EVIDENCE_PROCESSING_FAILED",
                    "severity": AlertSeverity.HIGH,
                    "title": f"Evidence Processing Failed for Document {doc.id}",
                    "message": f"Document '{doc.original_filename}' processing failed.",
                    "source_type": "evidence_documents",
                    "source_id": doc.id,
                    "state": "PROCESSING_FAILED",
                    "detected_at": doc.created_at,
                    "metadata": {"document_id": doc.id, "filename": doc.original_filename},
                })
            if doc.processing_status == "SECURITY_REJECTED":
                raw_dispute_alerts.append({
                    "category": AlertCategory.EVIDENCE,
                    "code": "EVIDENCE_SECURITY_REJECTED",
                    "severity": AlertSeverity.HIGH,
                    "title": f"Evidence Security Rejected for Document {doc.id}",
                    "message": f"Document '{doc.original_filename}' rejected for security/MIME violation.",
                    "source_type": "evidence_documents",
                    "source_id": doc.id,
                    "state": "SECURITY_REJECTED",
                    "detected_at": doc.created_at,
                    "metadata": {"document_id": doc.id, "filename": doc.original_filename},
                })

        # -------------------------------------------------------------------
        # Rule Category 6: POLICY
        # -------------------------------------------------------------------
        for pol in (d.policy_results or []):
            if pol.decision == "HUMAN_REVIEW":
                raw_dispute_alerts.append({
                    "category": AlertCategory.POLICY,
                    "code": "POLICY_REVIEW_REQUIRED",
                    "severity": AlertSeverity.MEDIUM,
                    "title": f"Policy Human Review Required for Dispute {d.id}",
                    "message": f"Policy evaluation result requires human review.",
                    "source_type": "policy_results",
                    "source_id": pol.id,
                    "state": "HUMAN_REVIEW",
                    "detected_at": pol.created_at,
                    "metadata": {"policy_result_id": pol.id, "decision": pol.decision},
                })
            if pol.outcome == "FAILED":
                raw_dispute_alerts.append({
                    "category": AlertCategory.POLICY,
                    "code": "POLICY_EVALUATION_FAILED",
                    "severity": AlertSeverity.HIGH,
                    "title": f"Policy Evaluation Failed for Dispute {d.id}",
                    "message": f"Policy evaluation failed for policy version {pol.policy_version}.",
                    "source_type": "policy_results",
                    "source_id": pol.id,
                    "state": "FAILED",
                    "detected_at": pol.created_at,
                    "metadata": {"policy_result_id": pol.id},
                })

        # -------------------------------------------------------------------
        # Rule Category 7: DATA INTEGRITY
        # -------------------------------------------------------------------
        for draft in (d.contest_drafts or []):
            if draft.status == "STALE" or draft.review_status == "STALE":
                raw_dispute_alerts.append({
                    "category": AlertCategory.DATA_INTEGRITY,
                    "code": "STALE_DRAFT",
                    "severity": AlertSeverity.HIGH,
                    "title": f"Stale Contest Draft for Dispute {d.id}",
                    "message": f"Contest draft {draft.id} is stale due to underlying evidence changes.",
                    "source_type": "contest_drafts",
                    "source_id": draft.id,
                    "state": "STALE",
                    "detected_at": draft.created_at,
                    "metadata": {"draft_id": draft.id, "fingerprint": draft.input_fingerprint},
                })

        for pref in (d.preflights or []):
            if pref.status == "BLOCKED" or pref.status == "STALE":
                raw_dispute_alerts.append({
                    "category": AlertCategory.DATA_INTEGRITY,
                    "code": "STALE_PREFLIGHT",
                    "severity": AlertSeverity.HIGH,
                    "title": f"Stale/Blocked Preflight for Dispute {d.id}",
                    "message": f"Preflight {pref.id} status is {pref.status}.",
                    "source_type": "contest_submission_preflights",
                    "source_id": pref.id,
                    "state": pref.status,
                    "detected_at": pref.created_at,
                    "metadata": {"preflight_id": pref.id, "status": pref.status},
                })

        # Check financial integrity
        if d.amount <= 0 or not d.payment_id or not d.currency:
            raw_dispute_alerts.append({
                "category": AlertCategory.DATA_INTEGRITY,
                "code": "FINANCIAL_INTEGRITY_VIOLATION",
                "severity": AlertSeverity.CRITICAL,
                "title": f"Financial Integrity Violation for Dispute {d.id}",
                "message": f"Dispute financial identity missing or invalid: amount={d.amount}, currency={d.currency}.",
                "source_type": "disputes",
                "source_id": d.id,
                "state": "FINANCIAL_VIOLATION",
                "detected_at": d.created_at,
                "metadata": {"dispute_id": d.id, "amount": d.amount, "payment_id": d.payment_id},
            })

        # -------------------------------------------------------------------
        # Rule Category 8: SECURITY
        # -------------------------------------------------------------------
        for aud in (d.submission_audits or []):
            meta = aud.sanitized_response_metadata or {}
            if meta.get("sanitized"):
                raw_dispute_alerts.append({
                    "category": AlertCategory.SECURITY,
                    "code": "CREDENTIAL_SECURITY_EXCEPTION",
                    "severity": AlertSeverity.CRITICAL,
                    "title": f"Credential Security Exception for Dispute {d.id}",
                    "message": f"Submission audit {aud.id} contained unsanitized credentials.",
                    "source_type": "contest_submission_audits",
                    "source_id": aud.id,
                    "state": "CREDENTIAL_UNSANITIZED",
                    "detected_at": aud.created_at,
                    "metadata": {"audit_id": aud.id},
                })

        # Process dispute raw_payload for security findings
        payload_str = json.dumps(d.raw_payload or {}).lower()
        if "ignore previous instructions" in payload_str or "system prompt" in payload_str:
            raw_dispute_alerts.append({
                "category": AlertCategory.SECURITY,
                "code": "SECURITY_REVIEW_REQUIRED",
                "severity": AlertSeverity.HIGH,
                "title": f"Prompt Injection Finding for Dispute {d.id}",
                "message": f"Potential prompt injection payload detected in dispute metadata.",
                "source_type": "disputes",
                "source_id": d.id,
                "state": "PROMPT_INJECTION",
                "detected_at": d.created_at,
                "metadata": {"dispute_id": d.id},
            })

        # -------------------------------------------------------------------
        # Rule Category 9: COMPLIANCE
        # -------------------------------------------------------------------
        for doc in docs:
            if doc.extraction and not doc.extraction.extracted_data:
                raw_dispute_alerts.append({
                    "category": AlertCategory.COMPLIANCE,
                    "code": "PROVENANCE_INCOMPLETE",
                    "severity": AlertSeverity.MEDIUM,
                    "title": f"Incomplete Provenance for Document {doc.id}",
                    "message": f"Document {doc.id} extraction is missing structured provenance.",
                    "source_type": "evidence_documents",
                    "source_id": doc.id,
                    "state": "PROVENANCE_INCOMPLETE",
                    "detected_at": doc.created_at,
                    "metadata": {"document_id": doc.id},
                })

        # Instantiate / Deduplicate Alerts
        for alert_dict in raw_dispute_alerts:
            fp = compute_alert_fingerprint(
                dispute_id=d.id,
                code=alert_dict["code"],
                source_type=alert_dict["source_type"],
                source_id=alert_dict["source_id"],
                state=alert_dict["state"],
            )
            detected_fps.add(fp)

            code = alert_dict["code"]
            sla_hours = SLA_MAP.get(code)
            detected_at = alert_dict["detected_at"]
            due_at = calculate_due_at(detected_at, sla_hours) if sla_hours else None

            # Calculate SLA-based severity escalation
            if due_at:
                _, _, sla_status, escalated_sev = calculate_sla_metrics(detected_at, due_at, now)
                if sla_status in ("OVERDUE", "CRITICAL_OVERDUE"):
                    alert_dict["severity"] = escalated_sev

            severity_str = alert_dict["severity"].value if isinstance(alert_dict["severity"], Enum) else alert_dict["severity"]
            category_str = alert_dict["category"].value if isinstance(alert_dict["category"], Enum) else alert_dict["category"]

            if severity_str == "CRITICAL":
                critical_count += 1
            elif severity_str == "HIGH":
                high_count += 1

            if fp in existing_by_fp:
                # Reuse existing alert record
                existing_alert = existing_by_fp[fp]
                existing_alert.detected_at = now
                if due_at:
                    existing_alert.due_at = due_at
                existing_alert.severity = severity_str
                existing_updated_count += 1
            else:
                # Insert new alert record
                new_alert = OperationalAlertModel(
                    dispute_id=d.id,
                    category=category_str,
                    code=code,
                    severity=severity_str,
                    status="OPEN",
                    title=alert_dict["title"],
                    message=alert_dict["message"],
                    source_type=alert_dict["source_type"],
                    source_id=alert_dict["source_id"],
                    detected_at=now,
                    due_at=due_at,
                    fingerprint=fp,
                    extra_metadata=_sanitize_alert_metadata(alert_dict.get("metadata", {})),
                    created_at=now,
                )
                new_alert_models.append(new_alert)

    # Auto-resolve alerts whose fingerprint is no longer active
    for fp, existing_alert in existing_by_fp.items():
        if fp not in detected_fps and existing_alert.status in ("OPEN", "ACKNOWLEDGED"):
            existing_alert.status = "RESOLVED"
            existing_alert.resolved_at = now

    if new_alert_models:
        db.add_all(new_alert_models)

    await db.commit()

    # Load all current OPEN / ACKNOWLEDGED alerts for response
    stmt_all = select(OperationalAlertModel).where(OperationalAlertModel.status.in_(["OPEN", "ACKNOWLEDGED"]))
    current_alerts_db = (await db.execute(stmt_all)).scalars().all()
    pydantic_alerts = [_model_to_schema(a) for a in current_alerts_db]

    return AlertDetectionResult(
        detected_count=len(current_alerts_db),
        new_count=len(new_alert_models),
        existing_count=existing_updated_count,
        critical_count=critical_count,
        high_count=high_count,
        alerts=pydantic_alerts,
    )


# ---------------------------------------------------------------------------
# Reporting & List Queries
# ---------------------------------------------------------------------------


async def get_alerts_summary(db: AsyncSession) -> OperationalAlertSummary:
    """Returns aggregated summary counts of active operational alerts."""
    stmt = select(OperationalAlertModel).where(OperationalAlertModel.status.in_(["OPEN", "ACKNOWLEDGED"]))
    alerts = (await db.execute(stmt)).scalars().all()

    now = datetime.utcnow()
    total_open = len(alerts)
    crit = sum(1 for a in alerts if a.severity == "CRITICAL")
    high = sum(1 for a in alerts if a.severity == "HIGH")
    med = sum(1 for a in alerts if a.severity == "MEDIUM")
    low = sum(1 for a in alerts if a.severity == "LOW")

    hum_rev = sum(1 for a in alerts if a.category == "HUMAN_REVIEW")
    sub = sum(1 for a in alerts if a.category == "SUBMISSION")
    rec = sum(1 for a in alerts if a.category == "RECONCILIATION")
    lifecycle = sum(1 for a in alerts if a.category == "LIFECYCLE")
    ev = sum(1 for a in alerts if a.category == "EVIDENCE")
    sec = sum(1 for a in alerts if a.category == "SECURITY")
    comp = sum(1 for a in alerts if a.category == "COMPLIANCE")

    overdue = sum(1 for a in alerts if a.due_at and a.due_at < now)

    return OperationalAlertSummary(
        total_open=total_open,
        critical_count=crit,
        high_count=high,
        medium_count=med,
        low_count=low,
        human_review_count=hum_rev,
        submission_count=sub,
        reconciliation_count=rec,
        lifecycle_count=lifecycle,
        evidence_count=ev,
        security_count=sec,
        compliance_count=comp,
        overdue_count=overdue,
    )


async def get_filtered_alerts(
    db: AsyncSession,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    dispute_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[OperationalAlert], int]:
    """Returns filtered, paginated alerts with hardcoded deterministic sorting."""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    query = select(OperationalAlertModel)

    if status:
        query = query.where(OperationalAlertModel.status == status)
    if severity:
        query = query.where(OperationalAlertModel.severity == severity)
    if category:
        query = query.where(OperationalAlertModel.category == category)
    if dispute_id:
        query = query.where(OperationalAlertModel.dispute_id == dispute_id)
    if date_from:
        query = query.where(OperationalAlertModel.detected_at >= date_from)
    if date_to:
        query = query.where(OperationalAlertModel.detected_at <= date_to)

    all_matches = (await db.execute(query)).scalars().all()
    total_count = len(all_matches)

    # Deterministic sorting: severity priority DESC -> due_at ASC (nulls last) -> detected_at ASC -> alert_id ASC
    def _sort_key(a: OperationalAlertModel):
        sev_prio = SEVERITY_PRIORITY.get(a.severity, 99)
        due_val = a.due_at.isoformat() if a.due_at else "9999-12-31"
        return (sev_prio, due_val, a.detected_at, a.id)

    all_matches.sort(key=_sort_key)
    paginated = all_matches[(page - 1) * page_size : page * page_size]

    return [_model_to_schema(a) for a in paginated], total_count


async def get_dispute_alert_detail(dispute_id: str, db: AsyncSession) -> DisputeAlertDetail:
    """Returns alert detail and history for a specific dispute."""
    stmt = select(OperationalAlertModel).where(OperationalAlertModel.dispute_id == dispute_id).order_by(OperationalAlertModel.detected_at.desc())
    alerts = (await db.execute(stmt)).scalars().all()

    current = [_model_to_schema(a) for a in alerts if a.status in ("OPEN", "ACKNOWLEDGED")]
    history = [_model_to_schema(a) for a in alerts]
    unresolved = [_model_to_schema(a) for a in alerts if a.status in ("OPEN", "ACKNOWLEDGED")]
    resolved = [_model_to_schema(a) for a in alerts if a.status in ("RESOLVED", "SUPPRESSED")]

    sev_summary: Dict[str, int] = {}
    for a in current:
        sev_summary[a.severity.value] = sev_summary.get(a.severity.value, 0) + 1

    return DisputeAlertDetail(
        dispute_id=dispute_id,
        current_alerts=current,
        alert_history=history,
        unresolved_alerts=unresolved,
        resolved_alerts=resolved,
        severity_summary=sev_summary,
    )


async def get_sla_monitoring_report(db: AsyncSession) -> SLAMonitoringReport:
    """Calculates deterministic SLA tracking metrics across all tracked operational items."""
    stmt = select(OperationalAlertModel).where(OperationalAlertModel.status.in_(["OPEN", "ACKNOWLEDGED"]))
    alerts = (await db.execute(stmt)).scalars().all()

    now = datetime.utcnow()
    items: List[SLAItem] = []
    on_time_count = 0
    warning_count = 0
    overdue_count = 0
    critical_overdue_count = 0
    total_elapsed_hours = 0.0

    by_category: Dict[str, int] = {}

    for a in alerts:
        elapsed, remaining, sla_stat, _ = calculate_sla_metrics(a.detected_at, a.due_at, now)
        total_elapsed_hours += elapsed

        if sla_stat == "ON_TIME":
            on_time_count += 1
        elif sla_stat == "WARNING":
            warning_count += 1
        elif sla_stat == "OVERDUE":
            overdue_count += 1
        elif sla_stat == "CRITICAL_OVERDUE":
            critical_overdue_count += 1

        by_category[a.category] = by_category.get(a.category, 0) + 1

        items.append(
            SLAItem(
                dispute_id=a.dispute_id,
                alert_code=a.code,
                detected_at=a.detected_at,
                due_at=a.due_at,
                elapsed_hours=elapsed,
                remaining_hours=remaining,
                sla_status=sla_stat,
            )
        )

    avg_elapsed = round(total_elapsed_hours / len(alerts), 2) if alerts else 0.0

    return SLAMonitoringReport(
        total_tracked=len(alerts),
        on_time=on_time_count,
        approaching_deadline=warning_count,
        overdue=overdue_count,
        critical_overdue=critical_overdue_count,
        average_elapsed_hours=avg_elapsed,
        by_category=by_category,
        items=items,
    )


async def get_operational_exceptions_report(db: AsyncSession) -> OperationalExceptionReport:
    """Aggregates operational exceptions by severity and domain category."""
    stmt = select(OperationalAlertModel).where(OperationalAlertModel.status.in_(["OPEN", "ACKNOWLEDGED"]))
    alerts = (await db.execute(stmt)).scalars().all()
    pydantic_alerts = [_model_to_schema(a) for a in alerts]

    crit = [a for a in pydantic_alerts if a.severity == AlertSeverity.CRITICAL]
    high = [a for a in pydantic_alerts if a.severity == AlertSeverity.HIGH]
    unresolved = [a for a in pydantic_alerts if a.status in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED)]

    stale = [a for a in pydantic_alerts if "STALE" in a.code or "OVERDUE" in a.code]
    sec = [a for a in pydantic_alerts if a.category == AlertCategory.SECURITY]
    fin = [a for a in pydantic_alerts if a.code == "FINANCIAL_INTEGRITY_VIOLATION"]
    comp = [a for a in pydantic_alerts if a.category == AlertCategory.COMPLIANCE]

    return OperationalExceptionReport(
        critical_exceptions=crit,
        high_exceptions=high,
        unresolved_exceptions=unresolved,
        stale_items=stale,
        security_exceptions=sec,
        financial_exceptions=fin,
        compliance_exceptions=comp,
    )


async def get_operational_health_report(db: AsyncSession) -> OperationalHealthReport:
    """Calculates high-level system health metrics from persisted records."""
    stmt_disp = select(func.count(Dispute.id))
    total_disputes = (await db.execute(stmt_disp)).scalar_one() or 0

    stmt_act = select(func.count(Dispute.id)).where(Dispute.status.in_(["open", "under_review", "action_required"]))
    active_disputes = (await db.execute(stmt_act)).scalar_one() or 0

    stmt_rev = select(func.count(ContestDraft.id)).where(ContestDraft.review_status == "PENDING_REVIEW")
    pending_reviews = (await db.execute(stmt_rev)).scalar_one() or 0

    stmt_blk = select(func.count(ContestDraft.id)).where(ContestDraft.status == "BLOCKED")
    blocked_drafts = (await db.execute(stmt_blk)).scalar_one() or 0

    stmt_unk = select(func.count(ContestSubmission.id)).where(ContestSubmission.state == "UNKNOWN")
    unknown_submissions = (await db.execute(stmt_unk)).scalar_one() or 0

    stmt_rec = select(func.count(ContestSubmission.id)).where(ContestSubmission.state == "UNKNOWN")
    reconciliation_required = (await db.execute(stmt_rec)).scalar_one() or 0

    stmt_act_req = select(func.count(Dispute.id)).where(Dispute.status == "action_required")
    action_required = (await db.execute(stmt_act_req)).scalar_one() or 0

    stmt_ev_fail = select(func.count(EvidenceDocument.id)).where(EvidenceDocument.processing_status == "FAILED")
    evidence_failures = (await db.execute(stmt_ev_fail)).scalar_one() or 0

    stmt_pol_fail = select(func.count(PolicyResult.id)).where(PolicyResult.outcome == "FAILED")
    policy_failures = (await db.execute(stmt_pol_fail)).scalar_one() or 0

    # Alerts
    stmt_crit = select(func.count(OperationalAlertModel.id)).where(and_(OperationalAlertModel.status.in_(["OPEN", "ACKNOWLEDGED"]), OperationalAlertModel.severity == "CRITICAL"))
    critical_alerts = (await db.execute(stmt_crit)).scalar_one() or 0

    stmt_high_a = select(func.count(OperationalAlertModel.id)).where(and_(OperationalAlertModel.status.in_(["OPEN", "ACKNOWLEDGED"]), OperationalAlertModel.severity == "HIGH"))
    high_alerts = (await db.execute(stmt_high_a)).scalar_one() or 0

    # Outcomes
    stmt_out = select(DisputeLifecycleSnapshot.outcome, func.count(DisputeLifecycleSnapshot.id)).group_by(DisputeLifecycleSnapshot.outcome)
    outcomes_rows = (await db.execute(stmt_out)).all()
    outcomes_dict = {row[0]: row[1] for row in outcomes_rows}

    return OperationalHealthReport(
        total_disputes=total_disputes,
        active_disputes=active_disputes,
        pending_reviews=pending_reviews,
        blocked_drafts=blocked_drafts,
        unknown_submissions=unknown_submissions,
        reconciliation_required=reconciliation_required,
        action_required=action_required,
        stale_items=unknown_submissions + blocked_drafts,
        evidence_failures=evidence_failures,
        policy_failures=policy_failures,
        critical_alerts=critical_alerts,
        high_alerts=high_alerts,
        final_outcomes=outcomes_dict,
    )


async def acknowledge_operational_alert(alert_id: str, db: AsyncSession) -> OperationalAlert:
    """Updates ONLY the OperationalAlert.status to ACKNOWLEDGED. Never mutates dispute business state."""
    stmt = select(OperationalAlertModel).where(OperationalAlertModel.id == alert_id)
    alert_model = (await db.execute(stmt)).scalars().first()

    if not alert_model:
        raise OperationalAlertException(f"Operational alert not found: {alert_id}", status_code=404)

    alert_model.status = "ACKNOWLEDGED"
    alert_model.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(alert_model)

    return _model_to_schema(alert_model)
