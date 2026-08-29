"""
Dispute Lifecycle Synchronization Service — Chargeback Shield Task 5.5

Implements a deterministic, read-only lifecycle state synchronization service for Razorpay disputes after contest submission.
Synchronizes external dispute processing status and final outcomes into immutable local snapshot records.

SAFETY & ARCHITECTURAL INVARIANTS:
- READ-ONLY AGAINST RAZORPAY: Uses strictly RazorpayClient.get_dispute(). ZERO mutation calls.
- SUBMISSION CONFIRMATION != FINAL OUTCOME: ContestSubmission.state is separate from DisputeOutcome.
- TERMINAL OUTCOME IMMUTABILITY: WON and LOST are terminal local outcomes. Never overwritten by unexpected polling data.
- ZERO AI / LLM calls. Financial identity and policy results remain 100% untouched.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.contest_submission_audit import ContestSubmissionAudit
from backend.app.models.dispute import Dispute
from backend.app.models.dispute_lifecycle_snapshot import DisputeLifecycleSnapshot
from backend.app.schemas.dispute_lifecycle_sync import (
    DisputeLifecycleStatus,
    DisputeLifecycleSyncResponse,
    DisputeOutcome,
    SyncResultType,
)
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


class DisputeLifecycleSyncException(Exception):
    """Raised when lifecycle synchronization fails due to invalid dispute ID or system error."""

    def __init__(self, message: str, status_code: int = 404):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Core Lifecycle Synchronization Service
# ---------------------------------------------------------------------------


async def sync_dispute_lifecycle(
    dispute_id: str,
    db: AsyncSession,
    razorpay_client: RazorpayClient | None = None,
) -> DisputeLifecycleSyncResponse:
    """
    Synchronizes the latest Razorpay dispute lifecycle state into local immutable snapshot records.
    Does NOT execute any Razorpay mutation operations.
    """
    db.expire_all()

    # 1. Fetch Dispute record
    stmt_dispute = (
        select(Dispute)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Dispute.policy_results),
            selectinload(Dispute.match_results),
            selectinload(Dispute.documents),
            selectinload(Dispute.submissions),
            selectinload(Dispute.lifecycle_snapshots),
        )
        .where(Dispute.id == dispute_id)
    )
    dispute = (await db.execute(stmt_dispute)).scalar_one_or_none()

    if not dispute:
        raise DisputeLifecycleSyncException(f"Dispute not found: {dispute_id}", status_code=404)

    # Load associated latest submission if present
    stmt_sub = (
        select(ContestSubmission)
        .where(ContestSubmission.dispute_id == dispute_id)
        .order_by(ContestSubmission.created_at.desc())
    )
    sub = (await db.execute(stmt_sub)).scalars().first()
    submission_id = sub.id if sub else None

    # Load latest lifecycle snapshot
    stmt_snap = (
        select(DisputeLifecycleSnapshot)
        .where(DisputeLifecycleSnapshot.dispute_id == dispute_id)
        .order_by(DisputeLifecycleSnapshot.created_at.desc())
    )
    prev_snapshot = (await db.execute(stmt_snap)).scalars().first()

    prev_status_enum = DisputeLifecycleStatus(prev_snapshot.new_lifecycle_status) if prev_snapshot else DisputeLifecycleStatus.UNKNOWN
    prev_outcome_enum = DisputeOutcome(prev_snapshot.outcome) if prev_snapshot else DisputeOutcome.PENDING

    now_utc = datetime.utcnow()

    # 2. Financial Safety Baseline
    payment_id_before = dispute.payment_id
    amount_before = dispute.amount
    currency_before = dispute.currency

    # 3. Read-Only External Razorpay Lookup
    try:
        if razorpay_client:
            resp = await razorpay_client.get_dispute(dispute_id)
            rzp_status = resp.status
            rzp_phase = resp.phase
            rzp_ref = resp.id
            raw_meta = resp.model_dump()
        else:
            rzp_service = RazorpayService(client=RazorpayClient())
            resp = await rzp_service.get_dispute(dispute_id)
            rzp_status = resp.status
            rzp_phase = resp.phase
            rzp_ref = resp.id
            raw_meta = resp.model_dump()

        # 4. Status & Outcome Mapping
        if rzp_status == "under_review":
            curr_status = DisputeLifecycleStatus.UNDER_REVIEW
            new_outcome = DisputeOutcome.UNDER_REVIEW
        elif rzp_status == "action_required":
            curr_status = DisputeLifecycleStatus.ACTION_REQUIRED
            new_outcome = DisputeOutcome.ACTION_REQUIRED
        elif rzp_status == "won":
            curr_status = DisputeLifecycleStatus.WON
            new_outcome = DisputeOutcome.WON
        elif rzp_status == "lost":
            curr_status = DisputeLifecycleStatus.LOST
            new_outcome = DisputeOutcome.LOST
        elif rzp_status in ("open", "closed"):
            curr_status = DisputeLifecycleStatus.SUBMITTED if sub and sub.state == "SUBMITTED" else DisputeLifecycleStatus.UNKNOWN
            new_outcome = DisputeOutcome.PENDING
        else:
            curr_status = DisputeLifecycleStatus.UNKNOWN_EXTERNAL_STATUS
            new_outcome = DisputeOutcome.UNKNOWN

        # 5. Terminal Outcome Protection & Transition Rules
        sync_result = SyncResultType.STATE_CHANGED
        transition_desc = f"{prev_status_enum.value} -> {curr_status.value}"

        # Rule A: Terminal Outcome Immutability
        if prev_outcome_enum in (DisputeOutcome.WON, DisputeOutcome.LOST):
            if new_outcome != prev_outcome_enum and new_outcome in (DisputeOutcome.WON, DisputeOutcome.LOST):
                logger.error(
                    "AUDIT [Final Outcome Conflict Attempt]: dispute_id=%s, prev_outcome=%s, new_outcome=%s",
                    dispute_id,
                    prev_outcome_enum.value,
                    new_outcome.value,
                )
                sync_result = SyncResultType.UNEXPECTED_TRANSITION
                new_outcome = prev_outcome_enum  # Terminal outcome remains unchanged!
                curr_status = prev_status_enum
            else:
                sync_result = SyncResultType.TERMINAL_REACHED
                new_outcome = prev_outcome_enum
                curr_status = prev_status_enum

        # Rule B: Unchanged state check
        elif prev_status_enum == curr_status and prev_outcome_enum == new_outcome:
            sync_result = SyncResultType.UNCHANGED
            transition_desc = f"{curr_status.value} (Unchanged)"

        # 6. Immutable Append-Only Snapshot Creation
        snapshot = DisputeLifecycleSnapshot(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            razorpay_dispute_id=dispute_id,
            submission_id=submission_id,
            previous_lifecycle_status=prev_status_enum.value,
            new_lifecycle_status=curr_status.value,
            razorpay_status=rzp_status,
            razorpay_phase=rzp_phase,
            razorpay_reference=rzp_ref,
            outcome=new_outcome.value,
            sync_result=sync_result.value,
            observed_at=now_utc,
            input_fingerprint=sub.input_fingerprint if sub else None,
        )
        db.add(snapshot)

        # 7. Audit Log Entry
        aud_rec = ContestSubmissionAudit(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            contest_submission_id=sub.id if sub else None,
            contest_draft_id=sub.contest_draft_id if sub else None,
            preflight_id=sub.preflight_id if sub else None,
            input_fingerprint=sub.input_fingerprint if sub else None,
            previous_state=prev_status_enum.value,
            new_state=curr_status.value,
            submission_status=sub.state if sub else "NONE",
            http_status_code=200,
            razorpay_reference_id=rzp_ref,
            sanitized_response_metadata=_sanitize_metadata({
                "action": "DISPUTE_LIFECYCLE_SYNC",
                "razorpay_status": rzp_status,
                "razorpay_phase": rzp_phase,
                "outcome": new_outcome.value,
                "sync_result": sync_result.value,
            }),
        )
        db.add(aud_rec)
        await db.commit()

        logger.info(
            "AUDIT [Dispute Lifecycle Sync Complete]: dispute_id=%s, rzp_status=%s, local_status=%s, outcome=%s, result=%s",
            dispute_id,
            rzp_status,
            curr_status.value,
            new_outcome.value,
            sync_result.value,
        )

        return DisputeLifecycleSyncResponse(
            dispute_id=dispute_id,
            razorpay_dispute_id=dispute_id,
            previous_status=prev_status_enum,
            current_status=curr_status,
            razorpay_status=rzp_status,
            razorpay_phase=rzp_phase,
            outcome=new_outcome,
            transition_type=transition_desc,
            synchronization_result=sync_result,
            snapshot_id=snapshot.id,
            audit_id=aud_rec.id,
            observed_at=now_utc,
        )

    except RazorpayNotFoundError as exc:
        reason_msg = f"Razorpay returned 404 Not Found during dispute status lookup: {exc}"
        logger.warning(
            "AUDIT [Dispute Lifecycle Sync 404 Ambiguity]: dispute_id=%s, error=%s",
            dispute_id,
            str(exc),
        )
        snapshot = DisputeLifecycleSnapshot(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            razorpay_dispute_id=dispute_id,
            submission_id=submission_id,
            previous_lifecycle_status=prev_status_enum.value,
            new_lifecycle_status=prev_status_enum.value,
            razorpay_status="NOT_FOUND_404",
            razorpay_phase=None,
            outcome=prev_outcome_enum.value,
            sync_result=SyncResultType.SYNC_FAILED.value,
            observed_at=now_utc,
        )
        db.add(snapshot)
        await db.commit()

        return DisputeLifecycleSyncResponse(
            dispute_id=dispute_id,
            razorpay_dispute_id=dispute_id,
            previous_status=prev_status_enum,
            current_status=prev_status_enum,
            razorpay_status="NOT_FOUND_404",
            razorpay_phase=None,
            outcome=prev_outcome_enum,
            transition_type=f"{prev_status_enum.value} (404 Lookup Failed)",
            synchronization_result=SyncResultType.SYNC_FAILED,
            snapshot_id=snapshot.id,
            audit_id=None,
            observed_at=now_utc,
        )

    except (RazorpayClientError, RazorpayAuthenticationError, RazorpayRateLimitError, RazorpayServerError, RazorpayNetworkError, Exception) as exc:
        reason_msg = f"Razorpay lookup failed ({type(exc).__name__}): {exc}"
        logger.error(
            "AUDIT [Dispute Lifecycle Sync Lookup Error]: dispute_id=%s, error=%s",
            dispute_id,
            str(exc),
        )
        snapshot = DisputeLifecycleSnapshot(
            id=str(uuid.uuid4()),
            dispute_id=dispute_id,
            razorpay_dispute_id=dispute_id,
            submission_id=submission_id,
            previous_lifecycle_status=prev_status_enum.value,
            new_lifecycle_status=prev_status_enum.value,
            razorpay_status="LOOKUP_ERROR",
            razorpay_phase=None,
            outcome=prev_outcome_enum.value,
            sync_result=SyncResultType.SYNC_FAILED.value,
            observed_at=now_utc,
        )
        db.add(snapshot)
        await db.commit()

        return DisputeLifecycleSyncResponse(
            dispute_id=dispute_id,
            razorpay_dispute_id=dispute_id,
            previous_status=prev_status_enum,
            current_status=prev_status_enum,
            razorpay_status="LOOKUP_ERROR",
            razorpay_phase=None,
            outcome=prev_outcome_enum,
            transition_type=f"{prev_status_enum.value} (Lookup Error)",
            synchronization_result=SyncResultType.SYNC_FAILED,
            snapshot_id=snapshot.id,
            audit_id=None,
            observed_at=now_utc,
        )

    finally:
        # 8. Post-execution Financial Safety Assertion
        await db.refresh(dispute)
        assert dispute.payment_id == payment_id_before, "CRITICAL FINANCIAL SAFETY VIOLATION: payment_id mutated during lifecycle sync"
        assert dispute.amount == amount_before, "CRITICAL FINANCIAL SAFETY VIOLATION: amount mutated during lifecycle sync"
        assert dispute.currency == currency_before, "CRITICAL FINANCIAL SAFETY VIOLATION: currency mutated during lifecycle sync"
