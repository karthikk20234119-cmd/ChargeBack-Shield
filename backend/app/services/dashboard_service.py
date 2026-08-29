"""
Dashboard Service Layer — Chargeback Shield Task 6.1

Provides deterministic, read-only operational dashboard analytics, paginated dispute listings,
360-degree dispute detail views, chronological lifecycle timelines, and active operational alert monitoring.

CRITICAL SAFETY & OBSERVABILITY INVARIANTS:
- READ-ONLY DB QUERIES: Consumes local DB records exclusively.
- ZERO RAZORPAY NETWORK CALLS: Does NOT import external Razorpay client classes or execute external HTTP lookups.
- NO BUSINESS MUTATIONS: Never mutates disputes, policy, evidence, matching, drafts, preflights, submissions, or lifecycle snapshots.
- FINANCIAL IMMUTABILITY: Asserts payment_id, amount, currency are untouched.
"""

from __future__ import annotations

import math
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.contest_draft import ContestDraft
from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.contest_submission_audit import ContestSubmissionAudit
from backend.app.models.contest_submission_preflight import ContestSubmissionPreflight
from backend.app.models.dispute import Dispute
from backend.app.models.dispute_lifecycle_snapshot import DisputeLifecycleSnapshot
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.matching import MatchResult
from backend.app.models.policy import PolicyResult
from backend.app.schemas.dashboard import (
    ActionRequiredItem,
    DashboardSummary,
    DisputeDashboardDetail,
    DisputeDashboardItem,
    DisputeListResponse,
    OperationalAlert,
    OutcomeSummary,
    ReconciliationRequiredItem,
    TimelineEvent,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DashboardException(Exception):
    """Raised when dashboard queries fail or resource is not found."""

    def __init__(self, message: str, status_code: int = 404):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Core Dashboard Service
# ---------------------------------------------------------------------------


async def get_dashboard_summary(db: AsyncSession) -> DashboardSummary:
    """Computes aggregate operational summary metrics across local Chargeback Shield records."""
    total_disputes = (await db.execute(select(func.count(Dispute.id)))).scalar() or 0
    evidence_uploaded = (await db.execute(select(func.count(EvidenceDocument.id)))).scalar() or 0
    evidence_processing = (
        await db.execute(select(func.count(EvidenceDocument.id)).where(EvidenceDocument.processing_status.in_(["INGESTED", "RUST_PARSED"])))
    ).scalar() or 0
    evidence_ready = (
        await db.execute(select(func.count(EvidenceDocument.id)).where(EvidenceDocument.processing_status == "AI_EXTRACTED"))
    ).scalar() or 0

    extraction_completed = (
        await db.execute(select(func.count(func.distinct(ExtractedEvidence.document_id))))
    ).scalar() or 0
    matching_completed = (
        await db.execute(select(func.count(func.distinct(MatchResult.dispute_id))))
    ).scalar() or 0

    eligible_count = (
        await db.execute(select(func.count(func.distinct(PolicyResult.dispute_id))).where(PolicyResult.decision == "ELIGIBLE"))
    ).scalar() or 0
    human_review_count = (
        await db.execute(select(func.count(func.distinct(PolicyResult.dispute_id))).where(PolicyResult.decision == "HUMAN_REVIEW"))
    ).scalar() or 0
    not_eligible_count = (
        await db.execute(select(func.count(func.distinct(PolicyResult.dispute_id))).where(PolicyResult.decision == "NOT_ELIGIBLE"))
    ).scalar() or 0

    drafts_pending_review = (
        await db.execute(select(func.count(ContestDraft.id)).where(ContestDraft.review_status == "PENDING_REVIEW"))
    ).scalar() or 0
    drafts_approved = (
        await db.execute(select(func.count(ContestDraft.id)).where(ContestDraft.review_status == "APPROVED"))
    ).scalar() or 0
    drafts_rejected = (
        await db.execute(select(func.count(ContestDraft.id)).where(ContestDraft.review_status == "REJECTED"))
    ).scalar() or 0

    preflight_ready = (
        await db.execute(select(func.count(ContestSubmissionPreflight.id)).where(ContestSubmissionPreflight.status == "READY"))
    ).scalar() or 0
    preflight_blocked = (
        await db.execute(select(func.count(ContestSubmissionPreflight.id)).where(ContestSubmissionPreflight.status == "BLOCKED"))
    ).scalar() or 0

    submissions_in_progress = (
        await db.execute(select(func.count(ContestSubmission.id)).where(ContestSubmission.state == "SUBMISSION_IN_PROGRESS"))
    ).scalar() or 0
    submissions_submitted = (
        await db.execute(select(func.count(ContestSubmission.id)).where(ContestSubmission.state == "SUBMITTED"))
    ).scalar() or 0
    submissions_unknown = (
        await db.execute(select(func.count(ContestSubmission.id)).where(ContestSubmission.state == "UNKNOWN"))
    ).scalar() or 0
    reconciliation_required = submissions_unknown

    under_review_count = (
        await db.execute(select(func.count(func.distinct(DisputeLifecycleSnapshot.dispute_id))).where(DisputeLifecycleSnapshot.outcome == "UNDER_REVIEW"))
    ).scalar() or 0
    action_required_count = (
        await db.execute(select(func.count(func.distinct(DisputeLifecycleSnapshot.dispute_id))).where(DisputeLifecycleSnapshot.outcome == "ACTION_REQUIRED"))
    ).scalar() or 0
    won_count = (
        await db.execute(select(func.count(func.distinct(DisputeLifecycleSnapshot.dispute_id))).where(DisputeLifecycleSnapshot.outcome == "WON"))
    ).scalar() or 0
    lost_count = (
        await db.execute(select(func.count(func.distinct(DisputeLifecycleSnapshot.dispute_id))).where(DisputeLifecycleSnapshot.outcome == "LOST"))
    ).scalar() or 0

    failed_operations = (
        await db.execute(select(func.count(ContestSubmission.id)).where(ContestSubmission.state == "FAILED"))
    ).scalar() or 0

    return DashboardSummary(
        total_disputes=total_disputes,
        evidence_uploaded=evidence_uploaded,
        evidence_processing=evidence_processing,
        evidence_ready=evidence_ready,
        extraction_completed=extraction_completed,
        matching_completed=matching_completed,
        eligible_count=eligible_count,
        human_review_count=human_review_count,
        not_eligible_count=not_eligible_count,
        drafts_pending_review=drafts_pending_review,
        drafts_approved=drafts_approved,
        drafts_rejected=drafts_rejected,
        preflight_ready=preflight_ready,
        preflight_blocked=preflight_blocked,
        submissions_in_progress=submissions_in_progress,
        submissions_submitted=submissions_submitted,
        submissions_unknown=submissions_unknown,
        reconciliation_required=reconciliation_required,
        under_review_count=under_review_count,
        action_required_count=action_required_count,
        won_count=won_count,
        lost_count=lost_count,
        failed_operations=failed_operations,
        generated_at=datetime.utcnow(),
    )


async def get_dashboard_disputes(
    db: AsyncSession,
    status: Optional[str] = None,
    policy_outcome: Optional[str] = None,
    review_status: Optional[str] = None,
    preflight_status: Optional[str] = None,
    submission_status: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
    outcome: Optional[str] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> DisputeListResponse:
    """Returns a paginated, safely filtered list of disputes for the dashboard."""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    query = select(Dispute).options(
        selectinload(Dispute.policy_results),
        selectinload(Dispute.contest_drafts),
        selectinload(Dispute.preflights),
        selectinload(Dispute.submissions),
        selectinload(Dispute.lifecycle_snapshots),
    )

    if status:
        query = query.where(Dispute.status == status)
    if created_from:
        query = query.where(Dispute.created_at >= created_from)
    if created_to:
        query = query.where(Dispute.created_at <= created_to)

    # Execute count
    count_query = select(func.count(Dispute.id))
    if status:
        count_query = count_query.where(Dispute.status == status)
    if created_from:
        count_query = count_query.where(Dispute.created_at >= created_from)
    if created_to:
        count_query = count_query.where(Dispute.created_at <= created_to)

    total_count = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Dispute.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    disputes = (await db.execute(query)).scalars().all()

    items: List[DisputeDashboardItem] = []
    for d in disputes:
        latest_pol = d.policy_results[0].decision if d.policy_results else None
        latest_draft = d.contest_drafts[0] if d.contest_drafts else None
        latest_pref = d.preflights[0].status if d.preflights else None
        latest_sub = d.submissions[0].state if d.submissions else None
        latest_snap = d.lifecycle_snapshots[0] if d.lifecycle_snapshots else None

        items.append(
            DisputeDashboardItem(
                dispute_id=d.id,
                payment_id=d.payment_id,
                amount=d.amount,
                currency=d.currency,
                dispute_status=d.status,
                policy_outcome=latest_pol,
                review_status=latest_draft.review_status if latest_draft else None,
                preflight_status=latest_pref,
                submission_status=latest_sub,
                lifecycle_status=latest_snap.new_lifecycle_status if latest_snap else None,
                outcome=latest_snap.outcome if latest_snap else None,
                created_at=d.created_at,
            )
        )

    # Post-filtering for joined attributes if requested
    if policy_outcome:
        items = [i for i in items if i.policy_outcome == policy_outcome]
    if review_status:
        items = [i for i in items if i.review_status == review_status]
    if preflight_status:
        items = [i for i in items if i.preflight_status == preflight_status]
    if submission_status:
        items = [i for i in items if i.submission_status == submission_status]
    if lifecycle_status:
        items = [i for i in items if i.lifecycle_status == lifecycle_status]
    if outcome:
        items = [i for i in items if i.outcome == outcome]

    total_pages = max(1, math.ceil(total_count / page_size))

    return DisputeListResponse(
        items=items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def get_dispute_dashboard_detail(dispute_id: str, db: AsyncSession) -> DisputeDashboardDetail:
    """Returns a unified 360-degree observability view for a single dispute."""
    db.expire_all()

    stmt = (
        select(Dispute)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Dispute.documents).selectinload(EvidenceDocument.extraction),
            selectinload(Dispute.match_results),
            selectinload(Dispute.policy_results),
            selectinload(Dispute.contest_drafts),
            selectinload(Dispute.preflights),
            selectinload(Dispute.submissions),
            selectinload(Dispute.submission_audits),
            selectinload(Dispute.lifecycle_snapshots),
        )
        .where(Dispute.id == dispute_id)
    )
    dispute = (await db.execute(stmt)).scalar_one_or_none()

    if not dispute:
        raise DashboardException(f"Dispute not found: {dispute_id}", status_code=404)

    # Financial Safety Baseline Capture
    payment_id_before = dispute.payment_id
    amount_before = dispute.amount
    currency_before = dispute.currency

    # Section 1: Dispute Summary
    dispute_dict = {
        "dispute_id": dispute.id,
        "payment_id": dispute.payment_id,
        "amount": dispute.amount,
        "currency": dispute.currency,
        "dispute_status": dispute.status,
        "phase": dispute.phase,
        "respond_by": dispute.respond_by.isoformat() if dispute.respond_by else None,
        "created_at": dispute.created_at.isoformat(),
    }

    # Section 2: Evidence Summary
    docs = dispute.documents or []
    extracted = [d.extraction for d in docs if d.extraction]
    evidence_dict = {
        "evidence_count": len(docs),
        "processing_status": "AI_EXTRACTED" if all(d.processing_status == "AI_EXTRACTED" for d in docs) and docs else ("PARTIAL" if docs else "NONE"),
        "extraction_status": "COMPLETED" if len(extracted) == len(docs) and docs else "PENDING",
        "document_types": [d.document_type for d in docs],
        "file_sizes_bytes": [d.file_size_bytes for d in docs],
        "hashes": [d.file_hash for d in docs],
        "processing_failures": [d.processing_error for d in docs if hasattr(d, "processing_error") and d.processing_error],
    }

    # Section 3: Matching Summary
    matches = dispute.match_results or []
    match_status_counts: Dict[str, int] = {}
    for m in matches:
        st = getattr(m, "status", "UNKNOWN")
        match_status_counts[st] = match_status_counts.get(st, 0) + 1
    matching_dict = {
        "total_matches": len(matches),
        "status_counts": match_status_counts,
        "rules_evaluated": [getattr(m, "fact_name", "fact") for m in matches],
    }

    # Section 4: Policy Summary
    policy = dispute.policy_results[0] if dispute.policy_results else None
    policy_dict = {
        "policy_result_id": policy.id if policy else None,
        "policy_outcome": policy.decision if policy else None,
        "policy_version": policy.policy_version if policy else None,
        "requires_human_review": policy.requires_human_review if policy else None,
        "critical_findings": policy.critical_findings if policy else [],
    }

    # Section 5: Contest Draft Summary
    draft = dispute.contest_drafts[0] if dispute.contest_drafts else None
    draft_dict = {
        "draft_id": draft.id if draft else None,
        "draft_status": draft.status if draft else None,
        "review_status": draft.review_status if draft else None,
        "draft_version": draft.draft_version if draft else None,
        "generator_version": draft.generator_version if draft else None,
        "input_fingerprint": draft.input_fingerprint if draft else None,
    }

    # Section 6: Preflight Summary
    preflight = dispute.preflights[0] if dispute.preflights else None
    preflight_dict = {
        "preflight_id": preflight.id if preflight else None,
        "preflight_status": preflight.status if preflight else None,
        "blocking_reasons": preflight.blocking_reasons if preflight else [],
        "warnings": preflight.warnings if preflight else [],
    }

    # Section 7: Submission Summary
    sub = dispute.submissions[0] if dispute.submissions else None
    sub_dict = {
        "submission_id": sub.id if sub else None,
        "submission_status": sub.state if sub else None,
        "submitted_at": sub.submitted_at.isoformat() if sub and sub.submitted_at else None,
        "reconciled_at": sub.reconciled_at.isoformat() if sub and sub.reconciled_at else None,
        "failure_category": sub.failure_category if sub else None,
        "failure_reason": sub.failure_reason if sub else None,
    }

    # Section 8: Razorpay Lifecycle Summary
    snapshot = dispute.lifecycle_snapshots[0] if dispute.lifecycle_snapshots else None
    lifecycle_dict = {
        "razorpay_status": snapshot.razorpay_status if snapshot else dispute.status,
        "razorpay_phase": snapshot.razorpay_phase if snapshot else dispute.phase,
        "local_lifecycle_status": snapshot.new_lifecycle_status if snapshot else "UNKNOWN",
        "outcome": snapshot.outcome if snapshot else "PENDING",
        "observed_at": snapshot.observed_at.isoformat() if snapshot else dispute.created_at.isoformat(),
    }

    # Section 9: Chronological Timeline Events
    timeline: List[TimelineEvent] = [
        TimelineEvent(
            timestamp=dispute.created_at,
            stage="DISPUTE_INGESTION",
            event_type="DISPUTE_CREATED",
            description=f"Dispute {dispute.id} ingested for payment {dispute.payment_id}",
            source_record=f"disputes:{dispute.id}",
        )
    ]

    for d in docs:
        timeline.append(
            TimelineEvent(
                timestamp=d.created_at,
                stage="EVIDENCE_INGESTION",
                event_type="DOCUMENT_UPLOADED",
                description=f"Document '{d.original_filename}' ({d.document_type}) uploaded",
                source_record=f"evidence_documents:{d.id}",
            )
        )
        if d.extraction:
            timeline.append(
                TimelineEvent(
                    timestamp=d.created_at,
                    stage="FACT_EXTRACTION",
                    event_type="FACTS_EXTRACTED",
                    description=f"Extracted facts for document {d.id}",
                    source_record=f"extracted_evidence:{d.extraction.id}",
                )
            )

    for m in matches:
        timeline.append(
            TimelineEvent(
                timestamp=m.created_at,
                stage="EVIDENCE_MATCHING",
                event_type="MATCH_EVALUATED",
                description=f"Rule {getattr(m, 'fact_name', 'fact')} evaluated to status {getattr(m, 'status', 'UNKNOWN')}",
                source_record=f"match_results:{m.id}",
            )
        )

    if policy:
        timeline.append(
            TimelineEvent(
                timestamp=policy.created_at,
                stage="POLICY_ENGINE",
                event_type="POLICY_EVALUATED",
                description=f"Policy decision evaluated: {policy.decision}",
                source_record=f"policy_results:{policy.id}",
            )
        )

    if draft:
        timeline.append(
            TimelineEvent(
                timestamp=draft.created_at,
                stage="RESPONSE_DRAFTING",
                event_type="DRAFT_GENERATED",
                description=f"Contest response draft generated with status {draft.status}",
                source_record=f"contest_drafts:{draft.id}",
            )
        )

    if preflight:
        timeline.append(
            TimelineEvent(
                timestamp=preflight.created_at,
                stage="PREFLIGHT_GATE",
                event_type="PREFLIGHT_EVALUATED",
                description=f"Submission preflight evaluated with status {preflight.status}",
                source_record=f"contest_submission_preflights:{preflight.id}",
            )
        )

    if sub:
        timeline.append(
            TimelineEvent(
                timestamp=sub.created_at,
                stage="CONTEST_SUBMISSION",
                event_type="SUBMISSION_ATTEMPTED",
                description=f"Contest submission executed with state {sub.state}",
                source_record=f"contest_submissions:{sub.id}",
            )
        )

    for snap in (dispute.lifecycle_snapshots or []):
        timeline.append(
            TimelineEvent(
                timestamp=snap.observed_at,
                stage="LIFECYCLE_SYNC",
                event_type="LIFECYCLE_SYNCHRONIZED",
                description=f"Razorpay status '{snap.razorpay_status}' synced to local outcome '{snap.outcome}'",
                source_record=f"dispute_lifecycle_snapshots:{snap.id}",
            )
        )

    timeline.sort(key=lambda x: x.timestamp)

    # Section 10: Operational Alerts Detection
    alerts = _detect_dispute_alerts(dispute, docs, policy, draft, preflight, sub, snapshot)

    # Financial Immutability Assertion
    assert dispute.payment_id == payment_id_before, "CRITICAL FINANCIAL SAFETY VIOLATION: payment_id mutated during dashboard read"
    assert dispute.amount == amount_before, "CRITICAL FINANCIAL SAFETY VIOLATION: amount mutated during dashboard read"
    assert dispute.currency == currency_before, "CRITICAL FINANCIAL SAFETY VIOLATION: currency mutated during dashboard read"

    return DisputeDashboardDetail(
        dispute=dispute_dict,
        evidence=evidence_dict,
        matching=matching_dict,
        policy=policy_dict,
        contest_draft=draft_dict,
        preflight=preflight_dict,
        submission=sub_dict,
        razorpay_lifecycle=lifecycle_dict,
        timeline=timeline,
        alerts=alerts,
    )


def _detect_dispute_alerts(
    dispute: Dispute,
    docs: List[EvidenceDocument],
    policy: Optional[PolicyResult],
    draft: Optional[ContestDraft],
    preflight: Optional[ContestSubmissionPreflight],
    sub: Optional[ContestSubmission],
    snapshot: Optional[DisputeLifecycleSnapshot],
) -> List[OperationalAlert]:
    """Detects deterministic operational alerts for a given dispute."""
    alerts: List[OperationalAlert] = []
    now = datetime.utcnow()

    # Alert 1: UNKNOWN submission state requires reconciliation
    if sub and sub.state == "UNKNOWN":
        alerts.append(
            OperationalAlert(
                alert_code="SUBMISSION_UNKNOWN",
                severity="WARNING",
                message=f"Contest submission attempt is in UNKNOWN state and requires reconciliation.",
                dispute_id=dispute.id,
                created_at=now,
            )
        )

    # Alert 2: Submissions stuck in IN_PROGRESS
    if sub and sub.state == "SUBMISSION_IN_PROGRESS":
        alerts.append(
            OperationalAlert(
                alert_code="SUBMISSION_IN_PROGRESS_TOO_LONG",
                severity="WARNING",
                message="Submission lock is currently IN_PROGRESS.",
                dispute_id=dispute.id,
                created_at=now,
            )
        )

    # Alert 3: Pending human review
    if draft and draft.review_status == "PENDING_REVIEW":
        alerts.append(
            OperationalAlert(
                alert_code="PENDING_HUMAN_REVIEW",
                severity="INFO",
                message="Contest draft is awaiting merchant review approval.",
                dispute_id=dispute.id,
                created_at=now,
            )
        )

    # Alert 4: Preflight blocked
    if preflight and preflight.status == "BLOCKED":
        alerts.append(
            OperationalAlert(
                alert_code="PRECHECK_BLOCKED",
                severity="WARNING",
                message=f"Submission preflight is BLOCKED: {', '.join(preflight.blocking_reasons or [])}",
                dispute_id=dispute.id,
                created_at=now,
            )
        )

    # Alert 5: Policy not eligible
    if policy and policy.decision == "NOT_ELIGIBLE":
        alerts.append(
            OperationalAlert(
                alert_code="POLICY_NOT_ELIGIBLE",
                severity="INFO",
                message="Policy engine evaluated dispute as NOT_ELIGIBLE for contest.",
                dispute_id=dispute.id,
                created_at=now,
            )
        )

    # Alert 6: Razorpay Action Required
    if snapshot and snapshot.outcome == "ACTION_REQUIRED":
        alerts.append(
            OperationalAlert(
                alert_code="RAZORPAY_ACTION_REQUIRED",
                severity="CRITICAL",
                message="Razorpay dispute requires merchant action.",
                dispute_id=dispute.id,
                created_at=now,
            )
        )

    # Alert 7: Evidence processing failure
    for d in docs:
        if d.processing_status == "FAILED":
            alerts.append(
                OperationalAlert(
                    alert_code="EVIDENCE_PROCESSING_FAILED",
                    severity="CRITICAL",
                    message=f"Document {d.original_filename} failed processing: {d.processing_error}",
                    dispute_id=dispute.id,
                    created_at=now,
                )
            )

    return alerts


async def get_dashboard_alerts(db: AsyncSession) -> List[OperationalAlert]:
    """Returns active operational alerts across all disputes."""
    alerts: List[OperationalAlert] = []

    # UNKNOWN submission alerts
    stmt_unk = select(ContestSubmission).where(ContestSubmission.state == "UNKNOWN")
    subs_unk = (await db.execute(stmt_unk)).scalars().all()
    for s in subs_unk:
        alerts.append(
            OperationalAlert(
                alert_code="SUBMISSION_UNKNOWN",
                severity="WARNING",
                message=f"Dispute {s.dispute_id} submission attempt is UNKNOWN; reconciliation required.",
                dispute_id=s.dispute_id,
                created_at=s.created_at,
            )
        )

    # Action required alerts
    stmt_act = select(DisputeLifecycleSnapshot).where(DisputeLifecycleSnapshot.outcome == "ACTION_REQUIRED")
    snaps_act = (await db.execute(stmt_act)).scalars().all()
    for snap in snaps_act:
        alerts.append(
            OperationalAlert(
                alert_code="RAZORPAY_ACTION_REQUIRED",
                severity="CRITICAL",
                message=f"Dispute {snap.dispute_id} requires merchant action on Razorpay.",
                dispute_id=snap.dispute_id,
                created_at=snap.observed_at,
            )
        )

    return alerts


async def get_reconciliation_required_disputes(db: AsyncSession) -> List[ReconciliationRequiredItem]:
    """Returns disputes requiring status reconciliation (UNKNOWN state)."""
    stmt = (
        select(ContestSubmission)
        .options(selectinload(ContestSubmission.dispute))
        .where(ContestSubmission.state == "UNKNOWN")
        .order_by(ContestSubmission.created_at.desc())
    )
    subs = (await db.execute(stmt)).scalars().all()

    items: List[ReconciliationRequiredItem] = []
    for s in subs:
        items.append(
            ReconciliationRequiredItem(
                dispute_id=s.dispute_id,
                submission_id=s.id,
                submitted_at=s.submitted_at,
                current_submission_status=s.state,
                last_reconciliation_at=s.reconciled_at,
                last_known_razorpay_status=s.razorpay_status,
                failure_reason=s.failure_reason,
            )
        )
    return items


async def get_action_required_disputes(db: AsyncSession) -> List[ActionRequiredItem]:
    """Returns disputes in Razorpay action_required status."""
    stmt = (
        select(DisputeLifecycleSnapshot)
        .options(
            selectinload(DisputeLifecycleSnapshot.dispute).selectinload(Dispute.policy_results),
            selectinload(DisputeLifecycleSnapshot.dispute).selectinload(Dispute.contest_drafts),
        )
        .where(DisputeLifecycleSnapshot.outcome == "ACTION_REQUIRED")
        .order_by(DisputeLifecycleSnapshot.observed_at.desc())
    )
    snaps = (await db.execute(stmt)).scalars().all()

    items: List[ActionRequiredItem] = []
    for snap in snaps:
        disp = snap.dispute
        pol = disp.policy_results[0].decision if disp and disp.policy_results else None
        draft = disp.contest_drafts[0].review_status if disp and disp.contest_drafts else None
        items.append(
            ActionRequiredItem(
                dispute_id=snap.dispute_id,
                payment_id=disp.payment_id if disp else "UNKNOWN",
                amount=disp.amount if disp else 0,
                currency=disp.currency if disp else "INR",
                razorpay_status=snap.razorpay_status,
                razorpay_phase=snap.razorpay_phase,
                respond_by=disp.respond_by if disp else None,
                policy_outcome=pol,
                review_status=draft,
                observed_at=snap.observed_at,
            )
        )
    return items


async def get_outcomes_summary(db: AsyncSession) -> OutcomeSummary:
    """Returns breakdown summary of dispute outcomes across all disputes."""
    stmt = select(
        DisputeLifecycleSnapshot.outcome,
        func.count(func.distinct(DisputeLifecycleSnapshot.dispute_id)),
    ).group_by(DisputeLifecycleSnapshot.outcome)

    rows = (await db.execute(stmt)).all()
    counts = {r[0]: r[1] for r in rows}

    won = counts.get("WON", 0)
    lost = counts.get("LOST", 0)
    under_review = counts.get("UNDER_REVIEW", 0)
    pending = counts.get("PENDING", 0)
    unknown = counts.get("UNKNOWN", 0)
    total = sum(counts.values())

    return OutcomeSummary(
        won_count=won,
        lost_count=lost,
        under_review_count=under_review,
        pending_count=pending,
        unknown_count=unknown,
        total_count=total,
    )
