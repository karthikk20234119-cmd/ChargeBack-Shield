"""
Contest Submission Preflight Service — Chargeback Shield Task 5.3

Provides deterministic local preflight authorization checks for local ContestDraft objects.
LOCAL ONLY. ZERO Razorpay mutation. ZERO AI/LLM calls. ZERO financial field modifications.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.models.contest_draft import ContestDraft as ContestDraftModel
from backend.app.models.contest_submission_preflight import ContestSubmissionPreflight
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.matching import MatchResult
from backend.app.models.policy import PolicyResult
from backend.app.schemas.contest_submission_preflight import (
    CheckSeverity,
    CheckStatus,
    ContestSubmissionPreflightResult,
    PreflightCheck,
    PreflightStatus,
)
from backend.app.services.contest_draft_fingerprint import compute_contest_draft_input_fingerprint

logger = logging.getLogger(__name__)

GENERATOR_VERSION = "contest-draft-v1.0.0"


class StaleDraftException(Exception):
    """Raised when the draft input fingerprint mismatches current database state (mapped to HTTP 409)."""
    pass


async def get_latest_draft_model(dispute_id: str, db: AsyncSession) -> Optional[ContestDraftModel]:
    """Retrieves the latest local ContestDraftModel for a dispute."""
    stmt = (
        select(ContestDraftModel)
        .where(ContestDraftModel.dispute_id == dispute_id)
        .order_by(
            ContestDraftModel.draft_version.desc(),
            ContestDraftModel.created_at.desc(),
            ContestDraftModel.id.desc(),
        )
    )
    res = await db.execute(stmt)
    return res.scalars().first()


async def run_preflight(
    dispute_id: str,
    db: AsyncSession,
) -> ContestSubmissionPreflightResult:
    """
    Executes deterministic local preflight authorization verification for a dispute's latest ContestDraft.
    LOCAL ONLY. ZERO Razorpay mutation. ZERO external calls.
    """
    if db is None:
        raise ValueError("Database session required.")

    db.expire_all()

    # 1. Fetch Dispute with PolicyResults, MatchResults, Documents, Extractions, and Drafts
    stmt_dispute = (
        select(Dispute)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Dispute.policy_results),
            selectinload(Dispute.match_results),
            selectinload(Dispute.documents).selectinload(EvidenceDocument.extraction),
            selectinload(Dispute.contest_drafts),
        )
        .where(Dispute.id == dispute_id)
    )

    res_dispute = await db.execute(stmt_dispute)
    dispute = res_dispute.scalar_one_or_none()

    if not dispute or not dispute.contest_drafts:
        raise ValueError(f"Dispute with ID '{dispute_id}' or associated draft not found.")

    # Financial Safety Assertion: Capture trusted financial identity before preflight
    payment_id_before = dispute.payment_id
    amount_before = dispute.amount
    currency_before = dispute.currency

    # 2. Get latest draft
    latest_draft = await get_latest_draft_model(dispute_id, db)
    if not latest_draft:
        raise ValueError(f"No contest draft found for dispute '{dispute_id}'.")

    policy_db = dispute.policy_results[0] if dispute.policy_results else None
    match_results = list(dispute.match_results) if dispute.match_results else []
    documents = list(dispute.documents) if dispute.documents else []

    # 3. Fingerprint Re-computation & Validation
    current_fingerprint = compute_contest_draft_input_fingerprint(
        dispute_id=dispute_id,
        payment_id=dispute.payment_id,
        amount=dispute.amount,
        currency=dispute.currency,
        policy_result_id=policy_db.id if policy_db else None,
        policy_version=policy_db.policy_version if policy_db else None,
        policy_outcome=policy_db.outcome if policy_db else None,
        match_results=match_results,
        documents=documents,
        generator_version=latest_draft.generator_version or GENERATOR_VERSION,
        draft_version=latest_draft.draft_version or "1.0",
    )

    if latest_draft.input_fingerprint and latest_draft.input_fingerprint != current_fingerprint:
        raise StaleDraftException(
            "Draft is stale: evidence, match results, or policy inputs have changed since draft generation."
        )

    # 4. Perform Checks Sequence
    checks: List[PreflightCheck] = []
    blocking_reasons: List[str] = []
    warnings: List[str] = []

    # --- Check 1: Financial Identity Verification ---
    fin_ok = (
        dispute.payment_id == payment_id_before
        and dispute.amount == amount_before
        and dispute.currency == currency_before
        and bool(dispute.payment_id)
        and dispute.amount > 0
    )
    if fin_ok:
        checks.append(
            PreflightCheck(
                check_code="FINANCIAL_IDENTITY_CHECK",
                status=CheckStatus.PASS,
                message=f"Financial identity verified: payment_id={dispute.payment_id}, amount={dispute.amount}, currency={dispute.currency}",
                severity=CheckSeverity.BLOCKING,
                source_ids=[dispute.id],
            )
        )
    else:
        checks.append(
            PreflightCheck(
                check_code="FINANCIAL_IDENTITY_CHECK",
                status=CheckStatus.FAIL,
                message="Financial identity field mismatch or invalid financial bounds detected",
                severity=CheckSeverity.BLOCKING,
                source_ids=[dispute.id],
            )
        )
        blocking_reasons.append("Financial identity mismatch or invalid bounds")

    # --- Check 2: Fingerprint Validation ---
    checks.append(
        PreflightCheck(
            check_code="FINGERPRINT_CHECK",
            status=CheckStatus.PASS,
            message=f"Canonical input fingerprint verified: {current_fingerprint[:12]}...",
            severity=CheckSeverity.BLOCKING,
            source_ids=[latest_draft.id],
        )
    )

    # --- Check 3: Policy Status Check ---
    if latest_draft.status == "BLOCKED":
        checks.append(
            PreflightCheck(
                check_code="POLICY_STATUS_CHECK",
                status=CheckStatus.FAIL,
                message="Contest draft policy status is BLOCKED",
                severity=CheckSeverity.BLOCKING,
                source_ids=[latest_draft.id],
            )
        )
        blocking_reasons.append("Contest draft policy status is BLOCKED")
    else:
        checks.append(
            PreflightCheck(
                check_code="POLICY_STATUS_CHECK",
                status=CheckStatus.PASS,
                message=f"Policy status on draft is '{latest_draft.status}'",
                severity=CheckSeverity.INFO,
                source_ids=[latest_draft.id],
            )
        )

    # --- Check 4: Review Approval Check ---
    review_stat = latest_draft.review_status or "PENDING_REVIEW"
    if review_stat == "APPROVED":
        checks.append(
            PreflightCheck(
                check_code="REVIEW_APPROVAL_CHECK",
                status=CheckStatus.PASS,
                message="Draft review status is APPROVED",
                severity=CheckSeverity.BLOCKING,
                source_ids=[latest_draft.id],
            )
        )
    else:
        checks.append(
            PreflightCheck(
                check_code="REVIEW_APPROVAL_CHECK",
                status=CheckStatus.FAIL,
                message=f"Draft review status is '{review_stat}' (APPROVED required)",
                severity=CheckSeverity.BLOCKING,
                source_ids=[latest_draft.id],
            )
        )
        blocking_reasons.append(f"Human review status is '{review_stat}' (APPROVED required)")

    # --- Check 5: Policy Consistency Check ---
    if not policy_db:
        checks.append(
            PreflightCheck(
                check_code="POLICY_CONSISTENCY_CHECK",
                status=CheckStatus.FAIL,
                message="PolicyResult is missing from database",
                severity=CheckSeverity.BLOCKING,
                source_ids=[dispute.id],
            )
        )
        blocking_reasons.append("Missing PolicyResult record")
    else:
        outcome_val = getattr(policy_db.outcome, "value", str(policy_db.outcome or ""))
        if outcome_val == "NOT_ELIGIBLE" and latest_draft.status != "BLOCKED":
            checks.append(
                PreflightCheck(
                    check_code="POLICY_CONSISTENCY_CHECK",
                    status=CheckStatus.FAIL,
                    message=f"Policy outcome is '{outcome_val}' which contradicts unblocked draft status",
                    severity=CheckSeverity.BLOCKING,
                    source_ids=[policy_db.id],
                )
            )
            blocking_reasons.append("Policy outcome NOT_ELIGIBLE contradicts draft status")
        else:
            checks.append(
                PreflightCheck(
                    check_code="POLICY_CONSISTENCY_CHECK",
                    status=CheckStatus.PASS,
                    message=f"PolicyResult outcome '{outcome_val}' matches draft policy state",
                    severity=CheckSeverity.INFO,
                    source_ids=[policy_db.id],
                )
            )

    # --- Check 6: Match Consistency Check ---
    critical_mismatches = [
        m for m in match_results
        if getattr(m, "is_critical", False) or getattr(m, "fact_name", "") in {"payment_id", "amount_minor"}
    ]
    failed_criticals = [
        m for m in critical_mismatches
        if getattr(getattr(m, "status", None), "value", str(getattr(m, "status", ""))) == "MISMATCH"
    ]
    if failed_criticals:
        checks.append(
            PreflightCheck(
                check_code="MATCH_CONSISTENCY_CHECK",
                status=CheckStatus.FAIL,
                message=f"Unresolved critical match failures detected ({len(failed_criticals)} critical mismatch)",
                severity=CheckSeverity.BLOCKING,
                source_ids=[str(getattr(m, "id", "")) for m in failed_criticals],
            )
        )
        blocking_reasons.append("Unresolved critical field mismatches in evidence")
    else:
        checks.append(
            PreflightCheck(
                check_code="MATCH_CONSISTENCY_CHECK",
                status=CheckStatus.PASS,
                message="No unresolved critical field mismatches found",
                severity=CheckSeverity.INFO,
                source_ids=[str(getattr(m, "id", "")) for m in match_results],
            )
        )

    # --- Check 7: Evidence Provenance Verification ---
    factual_args = latest_draft.factual_arguments
    if isinstance(factual_args, dict):
        if "arguments" in factual_args and isinstance(factual_args["arguments"], list):
            args_list = factual_args["arguments"]
        else:
            args_list = list(factual_args.values())
    elif isinstance(factual_args, list):
        args_list = factual_args
    else:
        args_list = []

    known_doc_ids = {str(d.id) for d in documents}
    known_match_ids = {str(m.id) for m in match_results}

    missing_doc_refs: List[str] = []
    missing_match_refs: List[str] = []

    # Check provenance pointers in factual_arguments
    for arg in args_list:
        if isinstance(arg, dict):
            doc_ids = arg.get("source_evidence_ids") or []
            match_ids = arg.get("source_match_result_ids") or []
        else:
            doc_ids = getattr(arg, "source_evidence_ids", []) or []
            match_ids = getattr(arg, "source_match_result_ids", []) or []

        for did in doc_ids:
            if did and str(did) not in known_doc_ids:
                missing_doc_refs.append(str(did))
        for mid in match_ids:
            if mid and str(mid) not in known_match_ids:
                missing_match_refs.append(str(mid))

    if missing_doc_refs or missing_match_refs:
        checks.append(
            PreflightCheck(
                check_code="EVIDENCE_PROVENANCE_CHECK",
                status=CheckStatus.FAIL,
                message=f"Evidence provenance broken: missing doc refs {missing_doc_refs}, missing match refs {missing_match_refs}",
                severity=CheckSeverity.BLOCKING,
                source_ids=missing_doc_refs + missing_match_refs,
            )
        )
        blocking_reasons.append("Factual argument evidence provenance broken or missing")
    else:
        checks.append(
            PreflightCheck(
                check_code="EVIDENCE_PROVENANCE_CHECK",
                status=CheckStatus.PASS,
                message=f"All evidence provenance references verified against {len(documents)} document(s)",
                severity=CheckSeverity.INFO,
                source_ids=list(known_doc_ids),
            )
        )

    # --- Check 8: Factual Argument Completeness ---
    if not args_list:
        checks.append(
            PreflightCheck(
                check_code="FACTUAL_ARGUMENT_CHECK",
                status=CheckStatus.FAIL,
                message="Factual arguments list is empty",
                severity=CheckSeverity.BLOCKING,
                source_ids=[latest_draft.id],
            )
        )
        blocking_reasons.append("Incomplete factual arguments: list is empty")
    else:
        checks.append(
            PreflightCheck(
                check_code="FACTUAL_ARGUMENT_CHECK",
                status=CheckStatus.PASS,
                message=f"Factual arguments verified ({len(args_list)} argument section(s))",
                severity=CheckSeverity.INFO,
                source_ids=[latest_draft.id],
            )
        )

    # --- Check 9: Unresolved Conflict Check ---
    review_flags = latest_draft.review_flags or {}
    unresolved_flags = [k for k, v in review_flags.items() if v is True]
    if unresolved_flags:
        warnings.append(f"Review flags present on draft: {unresolved_flags}")
        checks.append(
            PreflightCheck(
                check_code="UNRESOLVED_CONFLICT_CHECK",
                status=CheckStatus.WARN,
                message=f"Draft contains review flags: {unresolved_flags}",
                severity=CheckSeverity.WARNING,
                source_ids=[latest_draft.id],
            )
        )
    else:
        checks.append(
            PreflightCheck(
                check_code="UNRESOLVED_CONFLICT_CHECK",
                status=CheckStatus.PASS,
                message="No unresolved review flags present on draft",
                severity=CheckSeverity.INFO,
                source_ids=[latest_draft.id],
            )
        )

    # 5. Evaluate Overall Preflight Decision
    # Priority:
    # 1. BLOCKED if policy status BLOCKED, financial mismatch, missing policy, critical mismatch, broken provenance, or missing sections.
    # 2. REVIEW_REQUIRED if review_status != APPROVED.
    # 3. READY if all blocking checks pass and review_status == APPROVED.

    is_blocked = any(
        (c.status == CheckStatus.FAIL or getattr(c.status, "value", c.status) == "FAIL")
        and c.check_code != "REVIEW_APPROVAL_CHECK"
        for c in checks
    )
    is_review_required = review_stat != "APPROVED"

    if is_blocked or latest_draft.status == "BLOCKED":
        final_status = PreflightStatus.BLOCKED
    elif is_review_required:
        final_status = PreflightStatus.REVIEW_REQUIRED
    else:
        final_status = PreflightStatus.READY

    # 6. Financial Safety Post-Assertion
    assert dispute.payment_id == payment_id_before, "CRITICAL MUTATION DETECTED: payment_id mutated during preflight"
    assert dispute.amount == amount_before, "CRITICAL MUTATION DETECTED: amount mutated during preflight"
    assert dispute.currency == currency_before, "CRITICAL MUTATION DETECTED: currency mutated during preflight"

    preflight_uuid = str(uuid.uuid4())
    now_utc = datetime.utcnow()

    result_schema = ContestSubmissionPreflightResult(
        id=preflight_uuid,
        dispute_id=dispute_id,
        contest_draft_id=latest_draft.id,
        policy_result_id=policy_db.id if policy_db else None,
        status=final_status,
        draft_status=latest_draft.status,
        review_status=review_stat,
        input_fingerprint=current_fingerprint,
        draft_version=latest_draft.draft_version or "1.0",
        generator_version=latest_draft.generator_version or GENERATOR_VERSION,
        checks=checks,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        verified_financial_identity={
            "payment_id": dispute.payment_id,
            "amount": dispute.amount,
            "currency": dispute.currency,
        },
        verified_evidence_count=len(documents),
        generated_at=now_utc,
    )

    # 7. Persist Immutable Local Preflight Snapshot
    db_preflight = ContestSubmissionPreflight(
        id=preflight_uuid,
        dispute_id=dispute_id,
        contest_draft_id=latest_draft.id,
        policy_result_id=policy_db.id if policy_db else None,
        status=final_status.value,
        draft_status=latest_draft.status,
        review_status=review_stat,
        input_fingerprint=current_fingerprint,
        draft_version=latest_draft.draft_version or "1.0",
        generator_version=latest_draft.generator_version or GENERATOR_VERSION,
        checks=[c.model_dump() for c in checks],
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        verified_financial_identity={
            "payment_id": dispute.payment_id,
            "amount": dispute.amount,
            "currency": dispute.currency,
        },
        verified_evidence_count=len(documents),
        created_at=now_utc,
    )
    db.add(db_preflight)
    await db.commit()

    logger.info(
        f"AUDIT [Contest Submission Preflight Complete]: dispute_id={dispute_id}, "
        f"preflight_id={preflight_uuid}, status={final_status.value}, "
        f"draft_status={latest_draft.status}, review_status={review_stat}, "
        f"checks_count={len(checks)}, blocking_reasons_count={len(blocking_reasons)}"
    )

    return result_schema
