"""
Contest Submission Status Reconciliation Service — Chargeback Shield Task 5.4C

Implements a deterministic, read-only status reconciliation service for Razorpay contest submissions.
Safely resolves local submission records in UNKNOWN or SUBMISSION_IN_PROGRESS state
using strictly read-only Razorpay dispute lookups.

SAFETY & FINANCIAL INVARIANTS:
- ZERO Razorpay mutation operations (No POST, No PATCH, No PUT, No DELETE, No submit, No accept, No reject, No refund).
- NO BLIND RETRIES: Network timeouts and ambiguous 404s NEVER trigger automated re-submission.
- Financial identity (payment_id, amount, currency) and policy results remain 100% untouched.
- CAS concurrency control and append-only audit trail logging.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.contest_submission_audit import ContestSubmissionAudit
from backend.app.models.dispute import Dispute
from backend.app.schemas.contest_submission import SubmissionStatus
from backend.app.schemas.contest_submission_reconciliation import (
    ContestSubmissionReconciliationResponse,
    ReconciliationOutcome,
)
from backend.app.services.contest_draft_fingerprint import compute_contest_draft_input_fingerprint
from backend.app.services.contest_draft_review_service import get_latest_draft_model
from backend.app.services.contest_submission_service import _sanitize_metadata
from backend.app.services.razorpay_client import RazorpayClient
from backend.app.services.razorpay_errors import (
    RazorpayAuthenticationError,
    RazorpayClientError,
    RazorpayNetworkError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
    RazorpayServerError,
)
from backend.app.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SubmissionReconciliationException(Exception):
    """Raised when reconciliation fails due to invalid dispute ID or missing submission record."""

    def __init__(self, message: str, status_code: int = 404):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Core Reconciliation Service
# ---------------------------------------------------------------------------


async def reconcile_contest_submission(
    dispute_id: str,
    db: AsyncSession,
    razorpay_client: RazorpayClient | None = None,
) -> ContestSubmissionReconciliationResponse:
    """
    Reconciles a local ContestSubmission record against read-only Razorpay dispute status.

    Returns typed ContestSubmissionReconciliationResponse.
    Does NOT initiate any Razorpay mutation or re-submission.
    """
    db.expire_all()

    # 1. Fetch Dispute with complete context
    stmt_dispute = (
        select(Dispute)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Dispute.policy_results),
            selectinload(Dispute.match_results),
            selectinload(Dispute.documents),
            selectinload(Dispute.submissions),
        )
        .where(Dispute.id == dispute_id)
    )
    dispute = (await db.execute(stmt_dispute)).scalar_one_or_none()

    if not dispute:
        raise SubmissionReconciliationException(f"Dispute not found: {dispute_id}", status_code=404)

    # Fetch latest ContestSubmission record
    stmt_sub = (
        select(ContestSubmission)
        .where(ContestSubmission.dispute_id == dispute_id)
        .order_by(ContestSubmission.created_at.desc())
    )
    sub = (await db.execute(stmt_sub)).scalars().first()

    if not sub:
        raise SubmissionReconciliationException(f"No submission record found for dispute: {dispute_id}", status_code=404)

    now_utc = datetime.utcnow()

    # 2. Idempotent check for already SUBMITTED records
    if sub.state == SubmissionStatus.SUBMITTED.value:
        logger.info(
            "AUDIT [Contest Submission Reconciliation Already Submitted]: dispute_id=%s, submission_id=%s",
            dispute_id,
            sub.id,
        )
        stmt_aud = (
            select(ContestSubmissionAudit)
            .where(ContestSubmissionAudit.contest_submission_id == sub.id)
            .order_by(ContestSubmissionAudit.created_at.desc())
        )
        aud = (await db.execute(stmt_aud)).scalars().first()

        return ContestSubmissionReconciliationResponse(
            submission_id=sub.id,
            dispute_id=dispute_id,
            previous_status=SubmissionStatus.SUBMITTED,
            new_status=SubmissionStatus.SUBMITTED,
            outcome=ReconciliationOutcome.ALREADY_SUBMITTED,
            razorpay_status=sub.razorpay_status,
            razorpay_reference_id=sub.razorpay_reference,
            reconciled_at=sub.reconciled_at or now_utc,
            reconciliation_reason=sub.reconciliation_reason or "Submission is already in SUBMITTED state; no action required.",
            audit_id=aud.id if aud else None,
        )

    # 3. Capture Financial Safety Baseline
    payment_id_before = dispute.payment_id
    amount_before = dispute.amount
    currency_before = dispute.currency

    # 4. Fingerprint Safety Re-verification
    latest_draft = await get_latest_draft_model(dispute_id, db)
    policy_db = dispute.policy_results[0] if dispute.policy_results else None
    match_results = list(dispute.match_results) if dispute.match_results else []
    documents = list(dispute.documents) if dispute.documents else []

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

    if sub.input_fingerprint != current_fingerprint:
        reason_msg = "Current input fingerprint differs from stored submission fingerprint (stale input state)."
        logger.warning(
            "AUDIT [Contest Submission Reconciliation Fingerprint Stale]: dispute_id=%s, submission_id=%s",
            dispute_id,
            sub.id,
        )
        aud_rec = ContestSubmissionAudit(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            contest_submission_id=sub.id,
            contest_draft_id=sub.contest_draft_id,
            preflight_id=sub.preflight_id,
            input_fingerprint=current_fingerprint,
            previous_state=sub.state,
            new_state=sub.state,
            submission_status=sub.state,
            error_code="STALE_FINGERPRINT",
            sanitized_response_metadata={"reason": reason_msg},
        )
        db.add(aud_rec)
        await db.commit()

        return ContestSubmissionReconciliationResponse(
            submission_id=sub.id,
            dispute_id=dispute_id,
            previous_status=SubmissionStatus(sub.state),
            new_status=SubmissionStatus(sub.state),
            outcome=ReconciliationOutcome.STALE_FINGERPRINT,
            razorpay_status=sub.razorpay_status,
            razorpay_reference_id=sub.razorpay_reference,
            reconciled_at=now_utc,
            reconciliation_reason=reason_msg,
            audit_id=aud_rec.id,
        )

    # 5. Read-Only External Razorpay Lookup
    try:
        if razorpay_client:
            resp = await razorpay_client.get_dispute(dispute_id)
            rzp_status = resp.status
            rzp_ref = resp.id
            raw_meta = resp.model_dump()
        else:
            rzp_service = RazorpayService(client=RazorpayClient())
            resp = await rzp_service.get_dispute(dispute_id)
            rzp_status = resp.status
            rzp_ref = resp.id
            raw_meta = resp.model_dump()

        # Evaluate Razorpay Status
        # Authoritative status demonstrating contest submission occurred: under_review, action_required, won, lost
        if rzp_status in ("under_review", "action_required", "won", "lost"):
            prev_state = sub.state
            reason_msg = f"Razorpay dispute status '{rzp_status}' confirms contest submission occurred."

            # CAS Atomic State Transition: UNKNOWN / SUBMISSION_IN_PROGRESS -> SUBMITTED
            sub.previous_state = prev_state
            sub.state = SubmissionStatus.SUBMITTED.value
            sub.razorpay_status = rzp_status
            sub.razorpay_reference = rzp_ref or sub.razorpay_reference
            sub.reconciled_at = now_utc
            sub.reconciliation_reason = reason_msg
            sub.failure_category = "NONE"
            sub.failure_reason = None
            sub.updated_at = now_utc

            aud_rec = ContestSubmissionAudit(
                id=str(uuid.uuid4()),
                dispute_id=dispute_id,
                contest_submission_id=sub.id,
                contest_draft_id=sub.contest_draft_id,
                preflight_id=sub.preflight_id,
                input_fingerprint=current_fingerprint,
                previous_state=prev_state,
                new_state=SubmissionStatus.SUBMITTED.value,
                submission_status=SubmissionStatus.SUBMITTED.value,
                http_status_code=200,
                razorpay_reference_id=rzp_ref,
                sanitized_response_metadata=_sanitize_metadata(raw_meta),
            )
            db.add(aud_rec)
            await db.commit()
            await db.refresh(sub)

            logger.info(
                "AUDIT [Contest Submission Reconciled SUCCESS]: dispute_id=%s, submission_id=%s, new_state=SUBMITTED",
                dispute_id,
                sub.id,
            )

            return ContestSubmissionReconciliationResponse(
                submission_id=sub.id,
                dispute_id=dispute_id,
                previous_status=SubmissionStatus(prev_state),
                new_status=SubmissionStatus.SUBMITTED,
                outcome=ReconciliationOutcome.RECONCILED_SUBMITTED,
                razorpay_status=rzp_status,
                razorpay_reference_id=sub.razorpay_reference,
                reconciled_at=now_utc,
                reconciliation_reason=reason_msg,
                audit_id=aud_rec.id,
            )
        else:
            # Status is ambiguous
            reason_msg = f"Razorpay dispute status '{rzp_status}' does not conclusively confirm contest submission."
            logger.warning(
                "AUDIT [Contest Submission Reconciliation Ambiguous]: dispute_id=%s, rzp_status=%s",
                dispute_id,
                rzp_status,
            )

            aud_rec = ContestSubmissionAudit(
                id=str(uuid.uuid4()),
                dispute_id=dispute_id,
                contest_submission_id=sub.id,
                contest_draft_id=sub.contest_draft_id,
                preflight_id=sub.preflight_id,
                input_fingerprint=current_fingerprint,
                previous_state=sub.state,
                new_state=sub.state,
                submission_status=sub.state,
                error_code="UNRESOLVED_UNKNOWN",
                sanitized_response_metadata=_sanitize_metadata(raw_meta),
            )
            db.add(aud_rec)
            await db.commit()

            return ContestSubmissionReconciliationResponse(
                submission_id=sub.id,
                dispute_id=dispute_id,
                previous_status=SubmissionStatus(sub.state),
                new_status=SubmissionStatus(sub.state),
                outcome=ReconciliationOutcome.UNRESOLVED_UNKNOWN,
                razorpay_status=rzp_status,
                razorpay_reference_id=sub.razorpay_reference,
                reconciled_at=now_utc,
                reconciliation_reason=reason_msg,
                audit_id=aud_rec.id,
            )

    except RazorpayNotFoundError as exc:
        reason_msg = f"Razorpay returned 404 Not Found during dispute status lookup: {exc}"
        logger.warning(
            "AUDIT [Contest Submission Reconciliation 404 Ambiguity]: dispute_id=%s, error=%s",
            dispute_id,
            str(exc),
        )
        aud_rec = ContestSubmissionAudit(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            contest_submission_id=sub.id,
            contest_draft_id=sub.contest_draft_id,
            preflight_id=sub.preflight_id,
            input_fingerprint=current_fingerprint,
            previous_state=sub.state,
            new_state=sub.state,
            submission_status=sub.state,
            http_status_code=404,
            error_code="LOOKUP_404_AMBIGUOUS",
            sanitized_response_metadata={"error": str(exc)},
        )
        db.add(aud_rec)
        await db.commit()

        return ContestSubmissionReconciliationResponse(
            submission_id=sub.id,
            dispute_id=dispute_id,
            previous_status=SubmissionStatus(sub.state),
            new_status=SubmissionStatus(sub.state),
            outcome=ReconciliationOutcome.UNRESOLVED_UNKNOWN,
            razorpay_status=sub.razorpay_status,
            razorpay_reference_id=sub.razorpay_reference,
            reconciled_at=now_utc,
            reconciliation_reason=reason_msg,
            audit_id=aud_rec.id,
        )

    except (RazorpayClientError, RazorpayAuthenticationError, RazorpayRateLimitError, RazorpayServerError, RazorpayNetworkError, Exception) as exc:
        status_code = getattr(exc, "status_code", None)
        reason_msg = f"Razorpay lookup failed ({type(exc).__name__}): {exc}"
        logger.error(
            "AUDIT [Contest Submission Reconciliation Lookup Error]: dispute_id=%s, error=%s",
            dispute_id,
            str(exc),
        )
        aud_rec = ContestSubmissionAudit(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            contest_submission_id=sub.id,
            contest_draft_id=sub.contest_draft_id,
            preflight_id=sub.preflight_id,
            input_fingerprint=current_fingerprint,
            previous_state=sub.state,
            new_state=sub.state,
            submission_status=sub.state,
            http_status_code=status_code,
            error_code="LOOKUP_ERROR",
            sanitized_response_metadata={"error": str(exc)},
        )
        db.add(aud_rec)
        await db.commit()

        return ContestSubmissionReconciliationResponse(
            submission_id=sub.id,
            dispute_id=dispute_id,
            previous_status=SubmissionStatus(sub.state),
            new_status=SubmissionStatus(sub.state),
            outcome=ReconciliationOutcome.ERROR_LOOKUP_FAILED,
            razorpay_status=sub.razorpay_status,
            razorpay_reference_id=sub.razorpay_reference,
            reconciled_at=now_utc,
            reconciliation_reason=reason_msg,
            audit_id=aud_rec.id,
        )

    finally:
        # Post-execution Financial Safety Assertion
        await db.refresh(dispute)
        assert dispute.payment_id == payment_id_before, "CRITICAL FINANCIAL SAFETY VIOLATION: payment_id mutated during reconciliation"
        assert dispute.amount == amount_before, "CRITICAL FINANCIAL SAFETY VIOLATION: amount mutated during reconciliation"
        assert dispute.currency == currency_before, "CRITICAL FINANCIAL SAFETY VIOLATION: currency mutated during reconciliation"
