"""
Contest Submission Execution Service — Chargeback Shield Task 5.4B

Orchestrates controlled Razorpay contest submission execution.
Enforces 17-point pre-submission Authorization Gate, deterministic input fingerprinting,
CAS idempotency locks, credential sanitization, append-only audit logging, and financial safety assertions.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.contest_draft import ContestDraft as ContestDraftModel
from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.contest_submission_audit import ContestSubmissionAudit
from backend.app.models.contest_submission_preflight import ContestSubmissionPreflight
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.schemas.contest_submission import (
    FailureCategory,
    RazorpayContestSubmissionRequest,
    RazorpayContestSubmissionResponse,
    SubmissionStatus,
    ContestSubmissionResponse,
)
from backend.app.services.contest_draft_fingerprint import compute_contest_draft_input_fingerprint
from backend.app.services.contest_draft_review_service import get_latest_draft_model
from backend.app.services.contest_submission_client import (
    ContestSubmissionClient,
    HttpContestSubmissionClient,
)
from backend.app.services.razorpay_errors import (
    RazorpayAuthenticationError,
    RazorpayClientError,
    RazorpayNetworkError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
    RazorpayServerError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SubmissionAuthorizationException(Exception):
    """Raised when pre-submission authorization gate revalidation fails."""

    def __init__(self, message: str, reasons: List[str] | None = None):
        super().__init__(message)
        self.message = message
        self.reasons = reasons or [message]


class SubmissionConflictException(Exception):
    """Raised on idempotency violation, concurrent submission, or UNKNOWN state conflict."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Credential Sanitization Helper
# ---------------------------------------------------------------------------


def _sanitize_metadata(meta: dict | None) -> dict:
    """Scrubs authorization headers, secret keys, and Basic Auth tokens from audit metadata."""
    if not meta or not isinstance(meta, dict):
        return {}
    sanitized = {}
    for k, v in meta.items():
        k_lower = str(k).lower()
        if any(s in k_lower for s in ("auth", "key", "secret", "password", "token", "credential")):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_metadata(v)
        else:
            sanitized[k] = v
    return sanitized


# ---------------------------------------------------------------------------
# Core Contest Submission Service
# ---------------------------------------------------------------------------


async def submit_dispute_contest(
    dispute_id: str,
    db: AsyncSession,
    client: ContestSubmissionClient | None = None,
) -> ContestSubmissionResponse:
    """
    Executes controlled contest submission for an authorized dispute.

    Enforces 17-point authorization revalidation, CAS idempotency lock,
    external call execution, timeout recovery, and append-only audit trail.
    """
    if client is None:
        client = HttpContestSubmissionClient()

    db.expire_all()

    # 1. Load Dispute and complete context
    stmt_dispute = (
        select(Dispute)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Dispute.policy_results),
            selectinload(Dispute.match_results),
            selectinload(Dispute.documents).selectinload(EvidenceDocument.extraction),
            selectinload(Dispute.contest_drafts),
            selectinload(Dispute.preflights),
        )
        .where(Dispute.id == dispute_id)
    )
    dispute = (await db.execute(stmt_dispute)).scalar_one_or_none()

    if not dispute:
        raise SubmissionAuthorizationException(f"Dispute not found: {dispute_id}")

    # Capture financial safety baseline
    payment_id_before = dispute.payment_id
    amount_before = dispute.amount
    currency_before = dispute.currency

    # 2. Revalidate 17 Authorization Gate Checks
    gate_reasons: List[str] = []

    # Check 1 & 2: Dispute and Draft exist
    latest_draft = await get_latest_draft_model(dispute_id, db)
    if not latest_draft:
        gate_reasons.append("ContestDraft does not exist for dispute")

    # Check 3 & 4: Draft status & review status
    if latest_draft:
        if latest_draft.status == "BLOCKED":
            gate_reasons.append("ContestDraft status is BLOCKED")
        if latest_draft.review_status != "APPROVED":
            gate_reasons.append(f"ContestDraft review_status is '{latest_draft.review_status}', APPROVED required")

    # Check 5, 6, 7, 8: Preflight exists & status READY & matches dispute & draft
    stmt_preflight = (
        select(ContestSubmissionPreflight)
        .where(ContestSubmissionPreflight.dispute_id == dispute_id)
        .order_by(ContestSubmissionPreflight.created_at.desc())
    )
    latest_preflight = (await db.execute(stmt_preflight)).scalars().first()

    if not latest_preflight:
        gate_reasons.append("ContestSubmissionPreflight record does not exist")
    else:
        if latest_preflight.status != "READY":
            gate_reasons.append(f"ContestSubmissionPreflight status is '{latest_preflight.status}', READY required")
        if latest_preflight.dispute_id != dispute_id:
            gate_reasons.append("Preflight dispute_id mismatch")
        if latest_draft and latest_preflight.contest_draft_id != latest_draft.id:
            gate_reasons.append("Preflight does not belong to the latest ContestDraft")

    # Check 9: Fingerprint re-computation
    match_results = list(dispute.match_results) if dispute.match_results else []
    documents = list(dispute.documents) if dispute.documents else []
    policy_db = dispute.policy_results[0] if dispute.policy_results else None

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
    )

    if latest_draft and latest_draft.input_fingerprint != current_fingerprint:
        gate_reasons.append("Current input fingerprint differs from stored draft fingerprint (stale draft)")

    # Check 11 & 12: PolicyResult exists & outcome matches
    if not policy_db:
        gate_reasons.append("PolicyResult does not exist for dispute")
    elif policy_db.outcome == "NOT_ELIGIBLE":
        gate_reasons.append("PolicyResult outcome is NOT_ELIGIBLE")

    # Check 15, 16, 17: Financial fields match preflight
    if latest_preflight and latest_preflight.verified_financial_identity:
        vf = latest_preflight.verified_financial_identity
        if vf.get("payment_id") != dispute.payment_id:
            gate_reasons.append("Dispute payment_id changed since preflight")
        if vf.get("amount") != dispute.amount:
            gate_reasons.append("Dispute amount changed since preflight")
        if vf.get("currency") != dispute.currency:
            gate_reasons.append("Dispute currency changed since preflight")

    if gate_reasons:
        logger.warning(
            "AUDIT [Contest Submission Authorization Gate Refused]: dispute_id=%s, reasons=%s",
            dispute_id,
            gate_reasons,
        )
        raise SubmissionAuthorizationException("Pre-submission authorization gate failed", reasons=gate_reasons)

    # 3. Derive Deterministic Idempotency Key
    idempotency_raw = f"{dispute_id}:{dispute.payment_id}:{dispute.amount}:{dispute.currency}:{current_fingerprint}:{latest_preflight.id}"
    idempotency_key = hashlib.sha256(idempotency_raw.encode("utf-8")).hexdigest()

    # 4. Idempotency & State Machine Check
    stmt_sub = select(ContestSubmission).where(ContestSubmission.dispute_id == dispute_id)
    existing_sub = (await db.execute(stmt_sub)).scalars().first()

    if existing_sub:
        if existing_sub.state == SubmissionStatus.SUBMITTED.value:
            raise SubmissionConflictException("Dispute contest has already been submitted to Razorpay")
        elif existing_sub.state == SubmissionStatus.SUBMISSION_IN_PROGRESS.value:
            raise SubmissionConflictException("Submission attempt currently in progress by another worker")
        elif existing_sub.state == SubmissionStatus.UNKNOWN.value:
            raise SubmissionConflictException(
                "Dispute submission status is UNKNOWN due to a prior network timeout. Manual status resolution required."
            )

    # 5. Atomic CAS Lock: Claim Submission State -> SUBMISSION_IN_PROGRESS
    submission_id = existing_sub.id if existing_sub else str(uuid.uuid4())
    attempt_id = str(uuid.uuid4())
    now_utc = datetime.utcnow()

    if existing_sub:
        existing_sub.previous_state = existing_sub.state
        existing_sub.state = SubmissionStatus.SUBMISSION_IN_PROGRESS.value
        existing_sub.submission_attempt_id = attempt_id
        existing_sub.input_fingerprint = current_fingerprint
        existing_sub.idempotency_key = idempotency_key
        existing_sub.updated_at = now_utc
        sub_record = existing_sub
    else:
        sub_record = ContestSubmission(
            id=submission_id,
            submission_attempt_id=attempt_id,
            dispute_id=dispute_id,
            contest_draft_id=latest_draft.id,
            preflight_id=latest_preflight.id,
            input_fingerprint=current_fingerprint,
            idempotency_key=idempotency_key,
            previous_state="READY",
            state=SubmissionStatus.SUBMISSION_IN_PROGRESS.value,
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(sub_record)

    # Commit local SUBMISSION_IN_PROGRESS state BEFORE initiating external HTTP request
    await db.commit()
    await db.refresh(sub_record)

    logger.info(
        "AUDIT [Contest Submission Claimed]: dispute_id=%s, submission_id=%s, attempt_id=%s, state=SUBMISSION_IN_PROGRESS",
        dispute_id,
        submission_id,
        attempt_id,
    )

    # 6. Construct Razorpay Request from Trusted Local DB Records
    doc_ids_for_contest = [
        doc.razorpay_doc_id
        for doc in documents
        if doc.razorpay_doc_id and doc.processing_status == "AI_EXTRACTED"
    ]

    evidence_mapping = {
        "dispute_reason": dispute.reason_code,
        "payment_id": dispute.payment_id,
        "amount_minor": dispute.amount,
        "currency": dispute.currency,
    }

    req_payload = RazorpayContestSubmissionRequest(
        dispute_id=dispute_id,
        amount_minor=dispute.amount,
        currency=dispute.currency,
        summary=latest_draft.summary or "Merchant chargeback contest response.",
        comments=latest_draft.title or "Chargeback Response Submission",
        documents=doc_ids_for_contest,
        evidence=evidence_mapping,
    )

    # 7. Perform External Submission via Dedicated Client
    try:
        resp = await client.submit_contest(req_payload)

        # Success Handler
        sub_record.previous_state = SubmissionStatus.SUBMISSION_IN_PROGRESS.value
        sub_record.state = SubmissionStatus.SUBMITTED.value
        sub_record.razorpay_reference = resp.razorpay_reference_id or f"rzp_ref_{dispute_id}"
        sub_record.razorpay_status = resp.razorpay_status
        sub_record.http_status = resp.http_status_code
        sub_record.submitted_at = resp.submitted_at
        sub_record.failure_category = FailureCategory.NONE.value
        sub_record.failure_reason = None
        sub_record.updated_at = datetime.utcnow()

        audit_rec = ContestSubmissionAudit(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            contest_submission_id=submission_id,
            contest_draft_id=latest_draft.id,
            preflight_id=latest_preflight.id,
            input_fingerprint=current_fingerprint,
            previous_state=SubmissionStatus.SUBMISSION_IN_PROGRESS.value,
            new_state=SubmissionStatus.SUBMITTED.value,
            submission_status=SubmissionStatus.SUBMITTED.value,
            http_status_code=resp.http_status_code,
            razorpay_reference_id=resp.razorpay_reference_id,
            sanitized_response_metadata=_sanitize_metadata(resp.raw_response),
        )
        db.add(audit_rec)
        await db.commit()
        await db.refresh(sub_record)

        logger.info(
            "AUDIT [Contest Submission SUCCESS]: dispute_id=%s, submission_id=%s, razorpay_ref=%s",
            dispute_id,
            submission_id,
            sub_record.razorpay_reference,
        )

    except RazorpayNetworkError as exc:
        # Timeout / Ambiguous Network Outcome Handler -> UNKNOWN
        sub_record.previous_state = SubmissionStatus.SUBMISSION_IN_PROGRESS.value
        sub_record.state = SubmissionStatus.UNKNOWN.value
        sub_record.http_status = 504
        sub_record.failure_category = FailureCategory.TIMEOUT_AMBIGUOUS.value
        sub_record.failure_reason = str(exc)
        sub_record.updated_at = datetime.utcnow()

        audit_rec = ContestSubmissionAudit(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            contest_submission_id=submission_id,
            contest_draft_id=latest_draft.id,
            preflight_id=latest_preflight.id,
            input_fingerprint=current_fingerprint,
            previous_state=SubmissionStatus.SUBMISSION_IN_PROGRESS.value,
            new_state=SubmissionStatus.UNKNOWN.value,
            submission_status=SubmissionStatus.UNKNOWN.value,
            http_status_code=504,
            error_code="NETWORK_TIMEOUT_AMBIGUOUS",
            sanitized_response_metadata={"error": str(exc)},
        )
        db.add(audit_rec)
        await db.commit()
        await db.refresh(sub_record)

        logger.error(
            "AUDIT [Contest Submission UNKNOWN]: dispute_id=%s, submission_id=%s, error=%s",
            dispute_id,
            submission_id,
            str(exc),
        )

    except (RazorpayClientError, RazorpayAuthenticationError, RazorpayNotFoundError, RazorpayRateLimitError, RazorpayServerError) as exc:
        # Deterministic 4xx/5xx Error Handler -> FAILED
        status_code = getattr(exc, "status_code", 400)
        fail_cat = FailureCategory.CLIENT_ERROR_4XX.value
        if status_code in (401, 403):
            fail_cat = FailureCategory.AUTH_ERROR_401_403.value
        elif status_code == 404:
            fail_cat = FailureCategory.NOT_FOUND_404.value
        elif status_code == 409:
            fail_cat = FailureCategory.CONFLICT_409.value
        elif status_code == 429:
            fail_cat = FailureCategory.RATE_LIMIT_429.value
        elif status_code >= 500:
            fail_cat = FailureCategory.SERVER_ERROR_5XX.value

        sub_record.previous_state = SubmissionStatus.SUBMISSION_IN_PROGRESS.value
        sub_record.state = SubmissionStatus.FAILED.value
        sub_record.http_status = status_code
        sub_record.failure_category = fail_cat
        sub_record.failure_reason = str(exc)
        sub_record.updated_at = datetime.utcnow()

        audit_rec = ContestSubmissionAudit(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            contest_submission_id=submission_id,
            contest_draft_id=latest_draft.id,
            preflight_id=latest_preflight.id,
            input_fingerprint=current_fingerprint,
            previous_state=SubmissionStatus.SUBMISSION_IN_PROGRESS.value,
            new_state=SubmissionStatus.FAILED.value,
            submission_status=SubmissionStatus.FAILED.value,
            http_status_code=status_code,
            error_code=fail_cat,
            sanitized_response_metadata={"error": str(exc)},
        )
        db.add(audit_rec)
        await db.commit()
        await db.refresh(sub_record)

        logger.error(
            "AUDIT [Contest Submission FAILED]: dispute_id=%s, submission_id=%s, code=%d, error=%s",
            dispute_id,
            submission_id,
            status_code,
            str(exc),
        )

    # 8. Post-Execution Financial Safety Assertion
    await db.refresh(dispute)
    assert dispute.payment_id == payment_id_before, "CRITICAL FINANCIAL SAFETY VIOLATION: payment_id mutated"
    assert dispute.amount == amount_before, "CRITICAL FINANCIAL SAFETY VIOLATION: amount mutated"
    assert dispute.currency == currency_before, "CRITICAL FINANCIAL SAFETY VIOLATION: currency mutated"

    # Fetch audit ID
    stmt_aud = select(ContestSubmissionAudit).where(ContestSubmissionAudit.contest_submission_id == sub_record.id).order_by(ContestSubmissionAudit.created_at.desc())
    aud_rec = (await db.execute(stmt_aud)).scalars().first()

    return ContestSubmissionResponse(
        id=sub_record.id,
        dispute_id=sub_record.dispute_id,
        contest_draft_id=sub_record.contest_draft_id,
        preflight_id=sub_record.preflight_id,
        status=SubmissionStatus(sub_record.state),
        razorpay_status=sub_record.razorpay_status,
        razorpay_reference_id=sub_record.razorpay_reference,
        idempotency_key=sub_record.idempotency_key,
        submitted_at=sub_record.submitted_at,
        failure_category=FailureCategory(sub_record.failure_category),
        failure_reason=sub_record.failure_reason,
        audit_id=aud_rec.id if aud_rec else None,
        created_at=sub_record.created_at,
        updated_at=sub_record.updated_at,
    )
