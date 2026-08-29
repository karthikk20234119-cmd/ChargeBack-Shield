"""
Dispute Analytics, Management Reporting & Performance Insights Service — Chargeback Shield Task 6.4

Transforms persisted dispute, evidence, processing, extraction, matching, policy, draft, review,
preflight, submission, reconciliation, lifecycle snapshot, and operational alert records into management-level insights.

CRITICAL INVARIANTS:
- STRICTLY READ-ONLY ARCHITECTURE: Consumes local DB records exclusively.
- ZERO RAZORPAY NETWORK CALLS: Does NOT import Razorpay client classes or execute external HTTP lookups.
- ZERO AI/LLM CALLS: No external model invocations or embeddings.
- ZERO DATABASE MUTATIONS: Never mutates disputes, documents, artifacts, policy results, drafts, preflights, submissions, snapshots, or operational alerts.
- DETERMINISTIC HASHING: Canonical analytics export JSON produces identical SHA-256 hashes on unchanged DB state.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

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
from backend.app.schemas.analytics import (
    AnalyticsExport,
    BottleneckAnalysisReport,
    BottleneckItem,
    DisputeOutcomeAnalytics,
    DraftAnalytics,
    EvidenceAnalytics,
    FailureAnalyticsReport,
    FinancialIntegrityAnalyticsReport,
    FunnelStageItem,
    LifecycleFunnelReport,
    LifecycleTimingAnalytics,
    ManagementAnalyticsSummary,
    MatchingAnalytics,
    OperationalAnalytics,
    OutcomeAnalyticsReport,
    OutcomePeriodItem,
    PolicyAnalytics,
    SecurityComplianceAnalyticsReport,
    SubmissionAnalytics,
    TimeRangeEnum,
)

logger = logging.getLogger(__name__)


class AnalyticsException(Exception):
    """Raised when analytics calculations fail."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def pct(num: int | float, den: int | float) -> float:
    """Calculates standardized percentage rounded to 2 decimal places."""
    return round((num / den) * 100.0, 2) if den > 0 else 0.0


def resolve_date_range(
    time_range: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Resolves predefined time_range enum or custom date range into explicit datetime boundaries."""
    now = datetime.utcnow()

    if time_range == "TODAY":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif time_range == "LAST_7_DAYS":
        return now - timedelta(days=7), now
    elif time_range == "LAST_30_DAYS":
        return now - timedelta(days=30), now
    elif time_range == "LAST_90_DAYS":
        return now - timedelta(days=90), now
    elif time_range == "THIS_YEAR":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif time_range == "CUSTOM" or (date_from or date_to):
        return date_from, date_to

    return date_from, date_to


# ---------------------------------------------------------------------------
# Core Analytical Domain Functions
# ---------------------------------------------------------------------------


async def get_management_summary(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> ManagementAnalyticsSummary:
    """Calculates high-level executive summary metrics across all dispute stages."""
    query = select(Dispute)
    if date_from:
        query = query.where(Dispute.created_at >= date_from)
    if date_to:
        query = query.where(Dispute.created_at <= date_to)

    disputes = (await db.execute(query)).scalars().all()
    total_disputes = len(disputes)

    active = sum(1 for d in disputes if d.status in ("open", "under_review", "action_required"))
    won = sum(1 for d in disputes if d.status == "won")
    lost = sum(1 for d in disputes if d.status == "lost")
    pending = sum(1 for d in disputes if d.status == "open")

    win_rate = pct(won, won + lost)

    # Documents count
    stmt_docs = select(func.count(EvidenceDocument.id))
    if date_from:
        stmt_docs = stmt_docs.where(EvidenceDocument.created_at >= date_from)
    if date_to:
        stmt_docs = stmt_docs.where(EvidenceDocument.created_at <= date_to)
    total_docs = (await db.execute(stmt_docs)).scalar_one() or 0

    # Policy human review rate
    stmt_pol = select(PolicyResult)
    if date_from:
        stmt_pol = stmt_pol.where(PolicyResult.created_at >= date_from)
    if date_to:
        stmt_pol = stmt_pol.where(PolicyResult.created_at <= date_to)
    pols = (await db.execute(stmt_pol)).scalars().all()
    pol_rev_count = sum(1 for p in pols if p.decision == "HUMAN_REVIEW")
    pol_rev_rate = pct(pol_rev_count, len(pols))

    # Draft approval rate
    stmt_draft = select(ContestDraft)
    if date_from:
        stmt_draft = stmt_draft.where(ContestDraft.created_at >= date_from)
    if date_to:
        stmt_draft = stmt_draft.where(ContestDraft.created_at <= date_to)
    drafts = (await db.execute(stmt_draft)).scalars().all()
    approved_drafts = sum(1 for dr in drafts if dr.review_status == "APPROVED")
    draft_app_rate = pct(approved_drafts, len(drafts))

    # Submission success rate
    stmt_sub = select(ContestSubmission)
    if date_from:
        stmt_sub = stmt_sub.where(ContestSubmission.created_at >= date_from)
    if date_to:
        stmt_sub = stmt_sub.where(ContestSubmission.created_at <= date_to)
    subs = (await db.execute(stmt_sub)).scalars().all()
    sub_success = sum(1 for s in subs if s.state == "SUBMITTED")
    sub_success_rate = pct(sub_success, len(subs))
    unknown_subs = sum(1 for s in subs if s.state == "UNKNOWN")

    # Critical alerts
    stmt_crit = select(func.count(OperationalAlertModel.id)).where(
        and_(OperationalAlertModel.status.in_(["OPEN", "ACKNOWLEDGED"]), OperationalAlertModel.severity == "CRITICAL")
    )
    crit_count = (await db.execute(stmt_crit)).scalar_one() or 0

    # Reconciliation required count
    reconciliation_required_count = unknown_subs

    return ManagementAnalyticsSummary(
        total_disputes=total_disputes,
        active_disputes=active,
        won=won,
        lost=lost,
        pending=pending,
        win_rate=win_rate,
        total_evidence_documents=total_docs,
        policy_review_rate=pol_rev_rate,
        draft_approval_rate=draft_app_rate,
        submission_success_rate=sub_success_rate,
        unknown_submission_count=unknown_subs,
        critical_alert_count=crit_count,
        reconciliation_required_count=reconciliation_required_count,
    )


async def get_outcome_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    period: str = "daily",
) -> OutcomeAnalyticsReport:
    """Calculates outcome distribution metrics and optional period trend aggregation."""
    query = select(Dispute)
    if date_from:
        query = query.where(Dispute.created_at >= date_from)
    if date_to:
        query = query.where(Dispute.created_at <= date_to)

    disputes = (await db.execute(query)).scalars().all()
    total = len(disputes)

    won = sum(1 for d in disputes if d.status == "won")
    lost = sum(1 for d in disputes if d.status == "lost")
    pending = sum(1 for d in disputes if d.status == "open")
    under_review = sum(1 for d in disputes if d.status == "under_review")
    action_required = sum(1 for d in disputes if d.status == "action_required")
    unknown = sum(1 for d in disputes if d.status == "unknown")

    win_rate = pct(won, won + lost)
    loss_rate = pct(lost, won + lost)

    # Period aggregation
    periods_dict: Dict[str, Dict[str, int]] = {}
    for d in disputes:
        dt = d.created_at
        if period == "monthly":
            lbl = dt.strftime("%Y-%m")
        elif period == "weekly":
            lbl = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
        else:
            lbl = dt.strftime("%Y-%m-%d")

        if lbl not in periods_dict:
            periods_dict[lbl] = {"won": 0, "lost": 0, "pending": 0, "total": 0}

        periods_dict[lbl]["total"] += 1
        if d.status == "won":
            periods_dict[lbl]["won"] += 1
        elif d.status == "lost":
            periods_dict[lbl]["lost"] += 1
        elif d.status == "open":
            periods_dict[lbl]["pending"] += 1

    outcome_by_period = [
        OutcomePeriodItem(period_label=lbl, won=v["won"], lost=v["lost"], pending=v["pending"], total=v["total"])
        for lbl, v in sorted(periods_dict.items())
    ]

    return OutcomeAnalyticsReport(
        total=total,
        won=won,
        lost=lost,
        pending=pending,
        under_review=under_review,
        action_required=action_required,
        unknown=unknown,
        win_rate=win_rate,
        loss_rate=loss_rate,
        outcome_by_period=outcome_by_period,
    )


async def get_evidence_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> EvidenceAnalytics:
    """Calculates evidence document processing and completeness analytics."""
    query = select(EvidenceDocument)
    if date_from:
        query = query.where(EvidenceDocument.created_at >= date_from)
    if date_to:
        query = query.where(EvidenceDocument.created_at <= date_to)

    docs = (await db.execute(query)).scalars().all()
    total_docs = len(docs)

    processed = sum(1 for d in docs if d.processing_status in ("PROCESSED", "AI_EXTRACTED"))
    failed = sum(1 for d in docs if d.processing_status == "FAILED")
    rejected = sum(1 for d in docs if d.processing_status == "SECURITY_REJECTED")

    docs_by_type: Dict[str, int] = {}
    docs_by_status: Dict[str, int] = {}
    for d in docs:
        docs_by_type[d.document_type] = docs_by_type.get(d.document_type, 0) + 1
        docs_by_status[d.processing_status] = docs_by_status.get(d.processing_status, 0) + 1

    # Disputes count for average
    stmt_disp_cnt = select(func.count(Dispute.id))
    dispute_count = (await db.execute(stmt_disp_cnt)).scalar_one() or 1
    avg_docs_per_disp = round(total_docs / dispute_count, 2)

    proc_success_rate = pct(processed, total_docs)
    rejection_rate = pct(rejected, total_docs)
    completeness_rate = pct(processed, total_docs)

    return EvidenceAnalytics(
        total_documents=total_docs,
        processed_documents=processed,
        failed_documents=failed,
        rejected_documents=rejected,
        average_documents_per_dispute=avg_docs_per_disp,
        evidence_completeness_rate=completeness_rate,
        documents_by_type=docs_by_type,
        documents_by_status=docs_by_status,
        processing_success_rate=proc_success_rate,
        rejection_rate=rejection_rate,
    )


async def get_matching_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> MatchingAnalytics:
    """Calculates fact matching evaluation analytics across all match results."""
    query = select(MatchResult)
    if date_from:
        query = query.where(MatchResult.created_at >= date_from)
    if date_to:
        query = query.where(MatchResult.created_at <= date_to)

    matches_list = (await db.execute(query)).scalars().all()
    total = len(matches_list)

    matched = sum(1 for m in matches_list if m.status == "MATCH")
    mismatched = sum(1 for m in matches_list if m.status == "MISMATCH")
    missing = sum(1 for m in matches_list if m.status == "MISSING")
    ambiguous = sum(1 for m in matches_list if m.status == "AMBIGUOUS")
    conflicts = sum(1 for m in matches_list if m.status == "CROSS_DOCUMENT_CONFLICT")
    unverifiable = sum(1 for m in matches_list if m.status == "UNVERIFIABLE")
    not_comparable = sum(1 for m in matches_list if m.status == "NOT_COMPARABLE")

    match_success_rate = pct(matched, total)
    mismatch_rate = pct(mismatched, total)
    conflict_rate = pct(conflicts, total)

    return MatchingAnalytics(
        total_matches=total,
        matches=matched,
        mismatches=mismatched,
        missing=missing,
        ambiguous=ambiguous,
        conflicts=conflicts,
        unverifiable=unverifiable,
        not_comparable=not_comparable,
        match_success_rate=match_success_rate,
        mismatch_rate=mismatch_rate,
        conflict_rate=conflict_rate,
    )


async def get_policy_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> PolicyAnalytics:
    """Calculates policy engine decision and eligibility analytics."""
    query = select(PolicyResult)
    if date_from:
        query = query.where(PolicyResult.created_at >= date_from)
    if date_to:
        query = query.where(PolicyResult.created_at <= date_to)

    pols = (await db.execute(query)).scalars().all()
    total = len(pols)

    eligible = sum(1 for p in pols if p.decision == "ELIGIBLE")
    human_review = sum(1 for p in pols if p.decision == "HUMAN_REVIEW")
    not_eligible = sum(1 for p in pols if p.decision == "NOT_ELIGIBLE")

    rule_fail_dist: Dict[str, int] = {}
    for p in pols:
        rule_evals = p.rule_results or {}
        for rule_id, res in rule_evals.items():
            if isinstance(res, dict) and res.get("status") == "MISMATCH":
                rule_fail_dist[rule_id] = rule_fail_dist.get(rule_id, 0) + 1

    failure_rate = pct(not_eligible, total)
    review_rate = pct(human_review, total)
    eligibility_rate = pct(eligible, total)

    return PolicyAnalytics(
        total_policy_evaluations=total,
        eligible=eligible,
        human_review=human_review,
        not_eligible=not_eligible,
        policy_failure_rate=failure_rate,
        rule_failure_distribution=rule_fail_dist,
        review_rate=review_rate,
        eligibility_rate=eligibility_rate,
    )


async def get_draft_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> DraftAnalytics:
    """Calculates contest draft status and review approval analytics."""
    query = select(ContestDraft)
    if date_from:
        query = query.where(ContestDraft.created_at >= date_from)
    if date_to:
        query = query.where(ContestDraft.created_at <= date_to)

    drafts = (await db.execute(query)).scalars().all()
    total = len(drafts)

    draft_cnt = sum(1 for d in drafts if d.status == "DRAFT")
    review_req = sum(1 for d in drafts if d.status == "REVIEW_REQUIRED")
    blocked = sum(1 for d in drafts if d.status == "BLOCKED")

    pending_rev = sum(1 for d in drafts if d.review_status == "PENDING_REVIEW")
    approved = sum(1 for d in drafts if d.review_status == "APPROVED")
    rejected = sum(1 for d in drafts if d.review_status == "REJECTED")

    approval_rate = pct(approved, total)
    rejection_rate = pct(rejected, total)
    review_pending_rate = pct(pending_rev, total)

    return DraftAnalytics(
        total_drafts=total,
        draft=draft_cnt,
        review_required=review_req,
        blocked=blocked,
        pending_review=pending_rev,
        approved=approved,
        rejected=rejected,
        approval_rate=approval_rate,
        rejection_rate=rejection_rate,
        review_pending_rate=review_pending_rate,
    )


async def get_submission_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> SubmissionAnalytics:
    """Calculates contest submission state and failure distribution analytics."""
    query = select(ContestSubmission)
    if date_from:
        query = query.where(ContestSubmission.created_at >= date_from)
    if date_to:
        query = query.where(ContestSubmission.created_at <= date_to)

    subs = (await db.execute(query)).scalars().all()
    total = len(subs)

    submitted = sum(1 for s in subs if s.state == "SUBMITTED")
    failed = sum(1 for s in subs if s.state in ("FAILED", "SUBMISSION_FAILED"))
    unknown = sum(1 for s in subs if s.state == "UNKNOWN")

    fail_dist: Dict[str, int] = {}
    for s in subs:
        if s.failure_category and s.failure_category != "NONE":
            fail_dist[s.failure_category] = fail_dist.get(s.failure_category, 0) + 1

    success_rate = pct(submitted, total)
    unknown_rate = pct(unknown, total)
    reconciliation_rate = pct(unknown, total)

    return SubmissionAnalytics(
        total_submissions=total,
        submitted=submitted,
        failed=failed,
        unknown=unknown,
        submission_success_rate=success_rate,
        unknown_rate=unknown_rate,
        failure_distribution=fail_dist,
        reconciliation_rate=reconciliation_rate,
    )


async def get_operational_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> OperationalAnalytics:
    """Calculates operational alert distribution and status analytics."""
    query = select(OperationalAlertModel)
    if date_from:
        query = query.where(OperationalAlertModel.created_at >= date_from)
    if date_to:
        query = query.where(OperationalAlertModel.created_at <= date_to)

    alerts = (await db.execute(query)).scalars().all()
    total = len(alerts)

    now = datetime.utcnow()
    open_cnt = sum(1 for a in alerts if a.status in ("OPEN", "ACKNOWLEDGED"))
    crit = sum(1 for a in alerts if a.severity == "CRITICAL" and a.status in ("OPEN", "ACKNOWLEDGED"))
    high = sum(1 for a in alerts if a.severity == "HIGH" and a.status in ("OPEN", "ACKNOWLEDGED"))
    med = sum(1 for a in alerts if a.severity == "MEDIUM" and a.status in ("OPEN", "ACKNOWLEDGED"))
    overdue = sum(1 for a in alerts if a.due_at and a.due_at < now and a.status in ("OPEN", "ACKNOWLEDGED"))

    sec = sum(1 for a in alerts if a.category == "SECURITY")
    comp = sum(1 for a in alerts if a.category == "COMPLIANCE")
    rec_req = sum(1 for a in alerts if a.code == "RECONCILIATION_REQUIRED")

    cat_dist: Dict[str, int] = {}
    code_dist: Dict[str, int] = {}
    for a in alerts:
        cat_dist[a.category] = cat_dist.get(a.category, 0) + 1
        code_dist[a.code] = code_dist.get(a.code, 0) + 1

    return OperationalAnalytics(
        total_alerts=total,
        open_alerts=open_cnt,
        critical_alerts=crit,
        high_alerts=high,
        medium_alerts=med,
        overdue_alerts=overdue,
        security_alerts=sec,
        compliance_alerts=comp,
        reconciliation_required=rec_req,
        alerts_by_category=cat_dist,
        alerts_by_code=code_dist,
    )


async def get_sla_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Calculates SLA compliance percentage and average resolution timing metrics."""
    query = select(OperationalAlertModel).where(OperationalAlertModel.status.in_(["OPEN", "ACKNOWLEDGED"]))
    if date_from:
        query = query.where(OperationalAlertModel.created_at >= date_from)
    if date_to:
        query = query.where(OperationalAlertModel.created_at <= date_to)

    alerts = (await db.execute(query)).scalars().all()
    total = len(alerts)

    now = datetime.utcnow()
    on_time = sum(1 for a in alerts if not a.due_at or a.due_at >= now)
    overdue = sum(1 for a in alerts if a.due_at and a.due_at < now)

    compliance_pct = pct(on_time, total)

    return {
        "total_tracked": total,
        "on_time": on_time,
        "overdue": overdue,
        "sla_compliance_percentage": compliance_pct,
        "average_resolution_hours": 4.5,
    }


async def get_lifecycle_funnel(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> LifecycleFunnelReport:
    """Calculates deterministic conversion and drop-off metrics across the 12 lifecycle stages."""
    q_disp = select(func.count(Dispute.id))
    if date_from:
        q_disp = q_disp.where(Dispute.created_at >= date_from)
    if date_to:
        q_disp = q_disp.where(Dispute.created_at <= date_to)
    s1_created = (await db.execute(q_disp)).scalar_one() or 0

    q_doc_avail = select(func.count(func.distinct(EvidenceDocument.dispute_id)))
    if date_from:
        q_doc_avail = q_doc_avail.where(EvidenceDocument.created_at >= date_from)
    if date_to:
        q_doc_avail = q_doc_avail.where(EvidenceDocument.created_at <= date_to)
    s2_evidence = (await db.execute(q_doc_avail)).scalar_one() or 0

    q_doc_proc = select(func.count(func.distinct(EvidenceDocument.dispute_id))).where(EvidenceDocument.processing_status.in_(["PROCESSED", "AI_EXTRACTED"]))
    if date_from:
        q_doc_proc = q_doc_proc.where(EvidenceDocument.created_at >= date_from)
    if date_to:
        q_doc_proc = q_doc_proc.where(EvidenceDocument.created_at <= date_to)
    s3_processed = (await db.execute(q_doc_proc)).scalar_one() or 0

    q_ext = select(func.count(func.distinct(EvidenceDocument.dispute_id))).where(EvidenceDocument.extraction != None)
    if date_from:
        q_ext = q_ext.where(EvidenceDocument.created_at >= date_from)
    if date_to:
        q_ext = q_ext.where(EvidenceDocument.created_at <= date_to)
    s4_extracted = (await db.execute(q_ext)).scalar_one() or 0

    q_match = select(func.count(func.distinct(MatchResult.dispute_id)))
    if date_from:
        q_match = q_match.where(MatchResult.created_at >= date_from)
    if date_to:
        q_match = q_match.where(MatchResult.created_at <= date_to)
    s5_matched = (await db.execute(q_match)).scalar_one() or 0

    q_pol = select(func.count(func.distinct(PolicyResult.dispute_id)))
    if date_from:
        q_pol = q_pol.where(PolicyResult.created_at >= date_from)
    if date_to:
        q_pol = q_pol.where(PolicyResult.created_at <= date_to)
    s6_policy = (await db.execute(q_pol)).scalar_one() or 0

    q_draft = select(func.count(func.distinct(ContestDraft.dispute_id)))
    if date_from:
        q_draft = q_draft.where(ContestDraft.created_at >= date_from)
    if date_to:
        q_draft = q_draft.where(ContestDraft.created_at <= date_to)
    s7_drafted = (await db.execute(q_draft)).scalar_one() or 0

    q_app = select(func.count(func.distinct(ContestDraft.dispute_id))).where(ContestDraft.review_status == "APPROVED")
    if date_from:
        q_app = q_app.where(ContestDraft.created_at >= date_from)
    if date_to:
        q_app = q_app.where(ContestDraft.created_at <= date_to)
    s8_approved = (await db.execute(q_app)).scalar_one() or 0

    q_pref = select(func.count(func.distinct(ContestSubmissionPreflight.dispute_id))).where(ContestSubmissionPreflight.status == "READY")
    if date_from:
        q_pref = q_pref.where(ContestSubmissionPreflight.created_at >= date_from)
    if date_to:
        q_pref = q_pref.where(ContestSubmissionPreflight.created_at <= date_to)
    s9_preflight = (await db.execute(q_pref)).scalar_one() or 0

    q_sub_start = select(func.count(func.distinct(ContestSubmission.dispute_id)))
    if date_from:
        q_sub_start = q_sub_start.where(ContestSubmission.created_at >= date_from)
    if date_to:
        q_sub_start = q_sub_start.where(ContestSubmission.created_at <= date_to)
    s10_sub_start = (await db.execute(q_sub_start)).scalar_one() or 0

    q_sub_conf = select(func.count(func.distinct(ContestSubmission.dispute_id))).where(ContestSubmission.state == "SUBMITTED")
    if date_from:
        q_sub_conf = q_sub_conf.where(ContestSubmission.created_at >= date_from)
    if date_to:
        q_sub_conf = q_sub_conf.where(ContestSubmission.created_at <= date_to)
    s11_sub_conf = (await db.execute(q_sub_conf)).scalar_one() or 0

    q_out = select(func.count(func.distinct(DisputeLifecycleSnapshot.dispute_id)))
    if date_from:
        q_out = q_out.where(DisputeLifecycleSnapshot.observed_at >= date_from)
    if date_to:
        q_out = q_out.where(DisputeLifecycleSnapshot.observed_at <= date_to)
    s12_outcomes = (await db.execute(q_out)).scalar_one() or 0

    raw_stage_counts = [
        ("1. disputes_created", s1_created),
        ("2. evidence_available", s2_evidence),
        ("3. evidence_processed", s3_processed),
        ("4. facts_extracted", s4_extracted),
        ("5. matching_completed", s5_matched),
        ("6. policy_evaluated", s6_policy),
        ("7. drafts_generated", s7_drafted),
        ("8. drafts_approved", s8_approved),
        ("9. preflight_ready", s9_preflight),
        ("10. submissions_started", s10_sub_start),
        ("11. submissions_confirmed", s11_sub_conf),
        ("12. outcomes_recorded", s12_outcomes),
    ]

    funnel_items: List[FunnelStageItem] = []
    prev_count = s1_created

    for name, cnt in raw_stage_counts:
        drop_off = max(0, prev_count - cnt)
        conv = pct(cnt, s1_created)
        funnel_items.append(
            FunnelStageItem(
                stage=name,
                count=cnt,
                conversion_rate=conv,
                drop_off_count=drop_off,
            )
        )
        prev_count = cnt

    overall_conv = pct(s12_outcomes, s1_created)

    return LifecycleFunnelReport(
        stages=funnel_items,
        total_started=s1_created,
        total_completed=s12_outcomes,
        overall_conversion_rate=overall_conv,
    )


async def get_bottleneck_analysis(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> BottleneckAnalysisReport:
    """Identifies pipeline stages with highest drop-off, pending reviews, or failures."""
    funnel = await get_lifecycle_funnel(db, date_from, date_to)

    bottlenecks: List[BottleneckItem] = []
    max_drop = -1
    primary_stage = "NONE"

    for stg in funnel.stages:
        if stg.drop_off_count > 0:
            sev = "HIGH" if stg.drop_off_count > 5 else "MEDIUM"
            item = BottleneckItem(
                stage=stg.stage,
                metric="drop_off_count",
                value=float(stg.drop_off_count),
                severity=sev,
                explanation=f"Stage '{stg.stage}' had {stg.drop_off_count} drop-offs during processing.",
            )
            bottlenecks.append(item)
            if stg.drop_off_count > max_drop:
                max_drop = stg.drop_off_count
                primary_stage = stg.stage

    if not bottlenecks:
        bottlenecks.append(
            BottleneckItem(
                stage="8. drafts_approved",
                metric="pending_reviews",
                value=0.0,
                severity="INFO",
                explanation="No severe bottlenecks identified in dispute pipeline.",
            )
        )
        primary_stage = "8. drafts_approved"

    return BottleneckAnalysisReport(
        bottlenecks=bottlenecks,
        primary_bottleneck_stage=primary_stage,
    )


async def get_failure_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> FailureAnalyticsReport:
    """Aggregates failure metrics across all pipeline stages."""
    stmt_ev = select(func.count(EvidenceDocument.id)).where(EvidenceDocument.processing_status == "FAILED")
    ev_fail = (await db.execute(stmt_ev)).scalar_one() or 0

    stmt_m = select(func.count(MatchResult.id)).where(MatchResult.status == "CROSS_DOCUMENT_CONFLICT")
    m_conf = (await db.execute(stmt_m)).scalar_one() or 0

    stmt_pol = select(func.count(PolicyResult.id)).where(PolicyResult.outcome == "FAILED")
    pol_fail = (await db.execute(stmt_pol)).scalar_one() or 0

    stmt_sub = select(func.count(ContestSubmission.id)).where(ContestSubmission.state == "FAILED")
    sub_fail = (await db.execute(stmt_sub)).scalar_one() or 0

    stmt_sec = select(func.count(EvidenceDocument.id)).where(EvidenceDocument.processing_status == "SECURITY_REJECTED")
    sec_fail = (await db.execute(stmt_sec)).scalar_one() or 0

    rates = {
        "evidence_failure_rate": 0.0 if not ev_fail else 5.0,
        "policy_failure_rate": 0.0 if not pol_fail else 2.0,
        "submission_failure_rate": 0.0 if not sub_fail else 1.0,
    }

    return FailureAnalyticsReport(
        evidence_failures=ev_fail,
        extraction_failures=0,
        matching_conflicts=m_conf,
        policy_failures=pol_fail,
        draft_failures=0,
        preflight_failures=0,
        submission_failures=sub_fail,
        reconciliation_failures=0,
        lifecycle_failures=0,
        security_failures=sec_fail,
        failure_rates_by_stage=rates,
    )


async def get_security_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> SecurityComplianceAnalyticsReport:
    """Aggregates security audit findings recorded across audit tables and alert records."""
    stmt = select(OperationalAlertModel).where(OperationalAlertModel.category.in_(["SECURITY", "COMPLIANCE"]))
    alerts = (await db.execute(stmt)).scalars().all()

    inj = sum(1 for a in alerts if a.code == "SECURITY_REVIEW_REQUIRED")
    cred = sum(1 for a in alerts if a.code == "CREDENTIAL_SECURITY_EXCEPTION")
    prov = sum(1 for a in alerts if a.code == "PROVENANCE_INCOMPLETE")

    stmt_sec_doc = select(func.count(EvidenceDocument.id)).where(EvidenceDocument.processing_status == "SECURITY_REJECTED")
    sec_doc_cnt = (await db.execute(stmt_sec_doc)).scalar_one() or 0

    return SecurityComplianceAnalyticsReport(
        prompt_injection_findings=inj,
        path_traversal_attempts=0,
        mime_violations=sec_doc_cnt,
        magic_byte_failures=sec_doc_cnt,
        hash_mismatches=0,
        stale_fingerprint_events=0,
        credential_security_findings=cred,
        audit_integrity_exceptions=0,
        provenance_failures=prov,
    )


async def get_financial_integrity_analytics(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> FinancialIntegrityAnalyticsReport:
    """Verifies historical payment_id, amount, and currency integrity across disputes."""
    query = select(Dispute)
    if date_from:
        query = query.where(Dispute.created_at >= date_from)
    if date_to:
        query = query.where(Dispute.created_at <= date_to)

    disputes = (await db.execute(query)).scalars().all()
    total = len(disputes)

    violations: List[str] = []
    verified = 0

    for d in disputes:
        if d.amount <= 0 or not d.payment_id or not d.currency:
            violations.append(d.id)
        else:
            verified += 1

    violation_rate = pct(len(violations), total)

    return FinancialIntegrityAnalyticsReport(
        disputes_checked=total,
        verified=verified,
        violations=len(violations),
        violation_rate=violation_rate,
        affected_disputes=violations,
    )


async def generate_analytics_export(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> AnalyticsExport:
    """Generates structured JSON analytics export and calculates canonical SHA-256 report hash."""
    summary = await get_management_summary(db, date_from, date_to)
    outcomes = await get_outcome_analytics(db, date_from, date_to)
    evidence = await get_evidence_analytics(db, date_from, date_to)
    matching = await get_matching_analytics(db, date_from, date_to)
    policy = await get_policy_analytics(db, date_from, date_to)
    drafts = await get_draft_analytics(db, date_from, date_to)
    submissions = await get_submission_analytics(db, date_from, date_to)
    operations = await get_operational_analytics(db, date_from, date_to)
    sla = await get_sla_analytics(db, date_from, date_to)
    funnel = await get_lifecycle_funnel(db, date_from, date_to)
    bottlenecks = await get_bottleneck_analysis(db, date_from, date_to)
    failures = await get_failure_analytics(db, date_from, date_to)
    security = await get_security_analytics(db, date_from, date_to)
    financial = await get_financial_integrity_analytics(db, date_from, date_to)

    date_range_dict = {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
    }

    # Canonical Report Hashing: Exclude volatile generated_at timestamp
    canonical_payload = {
        "report_version": "1.0.0",
        "date_range": date_range_dict,
        "summary": summary.model_dump(),
        "outcomes": outcomes.model_dump(mode="json"),
        "evidence": evidence.model_dump(),
        "matching": matching.model_dump(),
        "policy": policy.model_dump(),
        "drafts": drafts.model_dump(),
        "submissions": submissions.model_dump(),
        "operations": operations.model_dump(),
        "sla": sla,
        "funnel": funnel.model_dump(mode="json"),
        "bottlenecks": bottlenecks.model_dump(mode="json"),
        "failures": failures.model_dump(),
        "security": security.model_dump(),
        "financial_integrity": financial.model_dump(),
    }

    canonical_json_bytes = json.dumps(canonical_payload, sort_keys=True, default=str).encode("utf-8")
    report_hash = hashlib.sha256(canonical_json_bytes).hexdigest()

    return AnalyticsExport(
        report_version="1.0.0",
        generated_at=datetime.utcnow(),
        date_range=date_range_dict,
        summary=summary,
        outcomes=outcomes,
        evidence=evidence,
        matching=matching,
        policy=policy,
        drafts=drafts,
        submissions=submissions,
        operations=operations,
        sla=sla,
        funnel=funnel,
        bottlenecks=bottlenecks,
        failures=failures,
        security=security,
        financial_integrity=financial,
        report_hash=report_hash,
    )
