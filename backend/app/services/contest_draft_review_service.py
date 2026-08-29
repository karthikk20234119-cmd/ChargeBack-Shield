"""
Contest Draft Review Service — Chargeback Shield Task 5.2

Provides deterministic human review workflow execution for local ContestDraft objects.
LOCAL ONLY. ZERO Razorpay mutation calls. ZERO AI calls. ZERO financial field modifications.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.models.contest_draft import ContestDraft as ContestDraftModel
from backend.app.models.contest_draft_review import ContestDraftReviewAudit
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.schemas.contest_draft import ContestDraft, ReviewStatus
from backend.app.schemas.contest_draft_review import (
    ContestDraftReviewResponse,
    ReviewDecision,
)
from backend.app.services.contest_draft_fingerprint import compute_contest_draft_input_fingerprint

logger = logging.getLogger(__name__)

GENERATOR_VERSION = "contest-draft-v1.0.0"


class StaleDraftException(Exception):
    """Raised when the draft fingerprint or latest-draft condition fails (mapped to HTTP 409)."""
    pass


class InvalidTransitionException(Exception):
    """Raised when an illegal state transition is attempted (mapped to HTTP 400)."""
    pass


class ConflictTransitionException(Exception):
    """Raised when a conflicting review transition is attempted on a terminal draft (mapped to HTTP 409)."""
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


async def get_latest_draft_schema(dispute_id: str, db: AsyncSession) -> ContestDraft:
    """Retrieves the latest ContestDraft Pydantic schema for API consumption."""
    draft_model = await get_latest_draft_model(dispute_id, db)
    if not draft_model:
        raise ValueError(f"No contest draft found for dispute '{dispute_id}'.")

    # Map model to Pydantic schema
    rev_status = ReviewStatus(draft_model.review_status) if draft_model.review_status else ReviewStatus.PENDING_REVIEW
    return ContestDraft(
        id=draft_model.id,
        dispute_id=draft_model.dispute_id,
        policy_result_id=draft_model.policy_result_id,
        draft_version=draft_model.draft_version,
        generator_version=draft_model.generator_version,
        status=draft_model.status,
        review_status=rev_status,
        title=draft_model.title,
        summary=draft_model.summary,
        dispute_context=draft_model.dispute_context or {},
        factual_arguments=draft_model.factual_arguments.get("arguments", []) if draft_model.factual_arguments else [],
        evidence_references=draft_model.evidence_references.get("references", []) if draft_model.evidence_references else [],
        limitations=draft_model.limitations.get("limitations", []) if draft_model.limitations else [],
        review_flags=draft_model.review_flags.get("flags", []) if draft_model.review_flags else [],
        input_fingerprint=draft_model.input_fingerprint,
        generated_at=draft_model.created_at,
    )


async def review_contest_draft(
    dispute_id: str,
    decision: ReviewDecision,
    comment: Optional[str] = None,
    reviewer_reference: str = "merchant_admin",
    db: AsyncSession = None,
) -> ContestDraftReviewResponse:
    """
    Executes a secure, deterministic human review for a local ContestDraft.
    LOCAL ONLY. ZERO Razorpay calls. ZERO AI calls.
    """
    if db is None:
        raise ValueError("Database session required.")

    db.expire_all()

    # 1. Fetch Dispute with PolicyResults, MatchResults, Documents, and Drafts
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

    # Financial Safety Assertion: Capture trusted financial identity before review
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

    # 3. Fingerprint Validation
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
            "Draft is stale: evidence or policy inputs have changed since draft generation."
        )

    # 4. State Machine Validation
    policy_status = latest_draft.status  # DRAFT, REVIEW_REQUIRED, BLOCKED
    prev_review_status = latest_draft.review_status or "PENDING_REVIEW"

    # Rule: BLOCKED drafts CANNOT be approved
    if policy_status == "BLOCKED" and decision == ReviewDecision.APPROVE:
        raise InvalidTransitionException("BLOCKED drafts cannot be approved.")

    # Rule: Terminal States & Idempotency
    if prev_review_status in ("APPROVED", "REJECTED"):
        target_terminal = "APPROVED" if decision == ReviewDecision.APPROVE else "REJECTED"
        if prev_review_status == target_terminal:
            # Idempotent success: Find existing audit and return HTTP 200 without duplicate audit
            stmt_audit = (
                select(ContestDraftReviewAudit)
                .where(ContestDraftReviewAudit.draft_id == latest_draft.id)
                .order_by(ContestDraftReviewAudit.created_at.desc())
            )
            existing_audit = (await db.execute(stmt_audit)).scalars().first()
            audit_id = existing_audit.id if existing_audit else "existing_audit"
            timestamp = existing_audit.created_at if existing_audit else datetime.utcnow()

            return ContestDraftReviewResponse(
                audit_id=audit_id,
                draft_id=latest_draft.id,
                dispute_id=dispute_id,
                previous_review_status=ReviewStatus(prev_review_status),
                new_review_status=ReviewStatus(prev_review_status),
                decision=decision,
                reviewer_reference=reviewer_reference,
                comment=comment,
                input_fingerprint=current_fingerprint,
                timestamp=timestamp,
            )
        else:
            # Conflicting transition on terminal state
            raise ConflictTransitionException(
                f"Draft is already in terminal review state '{prev_review_status}' and cannot be transitioned to '{target_terminal}'."
            )

    # 5. Atomic Conditional Update
    new_rev_status = "APPROVED" if decision == ReviewDecision.APPROVE else "REJECTED"
    stmt_update = (
        update(ContestDraftModel)
        .where(
            ContestDraftModel.id == latest_draft.id,
            ContestDraftModel.review_status == "PENDING_REVIEW",
        )
        .values(review_status=new_rev_status, updated_at=datetime.utcnow())
    )

    update_res = await db.execute(stmt_update)
    if update_res.rowcount == 0:
        await db.rollback()
        raise ConflictTransitionException("Concurrent review transition conflict. Another reviewer completed review.")

    # 6. Persist Append-Only Audit Log
    timestamp = datetime.utcnow()
    audit_record = ContestDraftReviewAudit(
        draft_id=latest_draft.id,
        dispute_id=dispute_id,
        previous_review_status=prev_review_status,
        new_review_status=new_rev_status,
        decision=decision.value,
        reviewer_reference=reviewer_reference,
        comment=comment,
        input_fingerprint=current_fingerprint,
        generator_version=latest_draft.generator_version or GENERATOR_VERSION,
        created_at=timestamp,
    )
    db.add(audit_record)
    await db.commit()
    await db.refresh(audit_record)

    # 7. Financial Immutability Assertion
    await db.refresh(dispute)
    assert dispute.payment_id == payment_id_before, "Financial safety invariant violated: payment_id mutated"
    assert dispute.amount == amount_before, "Financial safety invariant violated: amount mutated"
    assert dispute.currency == currency_before, "Financial safety invariant violated: currency mutated"

    logger.info(
        f"AUDIT [Contest Draft Review Complete]: dispute_id={dispute_id}, draft_id={latest_draft.id}, "
        f"previous_status={prev_review_status}, new_status={new_rev_status}, decision={decision.value}, reviewer={reviewer_reference}"
    )

    return ContestDraftReviewResponse(
        audit_id=audit_record.id,
        draft_id=latest_draft.id,
        dispute_id=dispute_id,
        previous_review_status=ReviewStatus(prev_review_status),
        new_review_status=ReviewStatus(new_rev_status),
        decision=decision,
        reviewer_reference=reviewer_reference,
        comment=comment,
        input_fingerprint=current_fingerprint,
        timestamp=timestamp,
    )
