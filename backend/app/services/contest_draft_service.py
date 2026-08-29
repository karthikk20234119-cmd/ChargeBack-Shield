"""
Explainable Contest Response Drafting Engine — Chargeback Shield Task 5.1

Consumes trusted Dispute data, ExtractedEvidence facts, MatchResult records, and PolicyResult
to generate human-reviewable ContestDraft objects.

CRITICAL SAFETY BOUNDARY:
- DRAFT GENERATION ONLY.
- ZERO Razorpay mutation API calls (submit, create, accept, reject dispute).
- ZERO LLM or embedding calls. 100% deterministic template generation.
- ZERO modification of dispute financial identity (payment_id, amount, currency).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.models.contest_draft import ContestDraft as ContestDraftModel
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.matching import MatchResult
from backend.app.models.policy import PolicyResult
from backend.app.schemas.contest_draft import (
    ContestDraft,
    ContestDraftStatus,
    EvidenceReference,
    FactualArgument,
    ReviewFlag,
)
from backend.app.schemas.matching import MatchStatus
from backend.app.schemas.policy import PolicyDecision
from backend.app.services.contest_draft_fingerprint import compute_contest_draft_input_fingerprint
from backend.app.services.contest_templates import (
    TEMPLATE_AMOUNT_MATCH,
    TEMPLATE_AMOUNT_MISMATCH,
    TEMPLATE_CROSS_DOCUMENT_CONFLICT,
    TEMPLATE_CURRENCY_MATCH,
    TEMPLATE_CURRENCY_MISMATCH,
    TEMPLATE_DELIVERY_DATE_INVALID,
    TEMPLATE_DELIVERY_DATE_MATCH,
    TEMPLATE_MISSING_EVIDENCE_SAFE,
    TEMPLATE_ORDER_ID_MATCH,
    TEMPLATE_ORDER_ID_MISMATCH,
    TEMPLATE_PROMPT_INJECTION_WARNING,
    TEMPLATE_SIGNATURE_VERIFIED,
    TEMPLATE_TRACKING_MATCH,
    TEMPLATE_TRACKING_MISMATCH,
    TEMPLATE_TRANSACTION_IDENTITY_MATCH,
    TEMPLATE_UNVERIFIABLE_FIELD,
    format_amount_display,
)
from backend.app.services.policy_engine_service import evaluate_dispute_policy

logger = logging.getLogger(__name__)

GENERATOR_VERSION = "contest-draft-v1.0.0"
DRAFT_VERSION = "1.0"


async def generate_contest_draft(
    dispute_id: str,
    db: AsyncSession,
    reference_date: str = "2026-08-26",
) -> ContestDraft:
    """
    Generates a structured, evidence-grounded, human-reviewable ContestDraft for a dispute.
    Pure deterministic execution with ZERO LLM calls and ZERO Razorpay mutation API calls.
    """
    db.expire_all()

    # 1. Fetch Dispute Record with PolicyResult, MatchResults, and Documents
    stmt = (
        select(Dispute)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Dispute.policy_results),
            selectinload(Dispute.match_results),
            selectinload(Dispute.documents).selectinload(EvidenceDocument.extraction),
        )
        .where(Dispute.id == dispute_id)
    )

    res = await db.execute(stmt)
    dispute = res.scalar_one_or_none()

    if not dispute:
        raise ValueError(f"Dispute with ID '{dispute_id}' not found.")

    # Financial Safety Assertion: Capture trusted financial identity before drafting
    payment_id_before = dispute.payment_id
    amount_before = dispute.amount
    currency_before = dispute.currency

    # Ensure PolicyResult exists
    policy_db = dispute.policy_results[0] if dispute.policy_results else None
    if not policy_db:
        policy_schema = await evaluate_dispute_policy(dispute_id, db, reference_date=reference_date)
        res = await db.execute(stmt)
        dispute = res.scalar_one_or_none()
        policy_db = dispute.policy_results[0] if dispute.policy_results else None

    # Retrieve Policy Decision
    policy_outcome_str = policy_db.outcome if policy_db else "HUMAN_REVIEW"
    policy_decision = PolicyDecision(policy_outcome_str)

    match_results: List[MatchResult] = list(dispute.match_results) if dispute.match_results else []
    documents: List[EvidenceDocument] = list(dispute.documents) if dispute.documents else []

    # Map EvidenceReferences
    evidence_refs: List[EvidenceReference] = []
    for doc in documents:
        doc_type = doc.document_type or "evidence"
        if doc.extraction and doc.extraction.document_type:
            doc_type = doc.extraction.document_type
        evidence_refs.append(
            EvidenceReference(
                evidence_id=doc.id,
                evidence_type=doc_type,
                document_name=doc.original_filename or "document.png",
                source_page=1,
                description=f"{doc_type.capitalize()} evidence document uploaded for dispute verification.",
            )
        )

    factual_arguments: List[FactualArgument] = []
    review_flags: List[ReviewFlag] = []
    limitations: List[str] = []

    arg_counter = 1

    def next_arg_id() -> str:
        nonlocal arg_counter
        aid = f"ARG_{arg_counter:03d}"
        arg_counter += 1
        return aid

    # -------------------------------------------------------------
    # CASE TYPE A: BLOCKED (NOT_ELIGIBLE)
    # -------------------------------------------------------------
    if policy_decision == PolicyDecision.NOT_ELIGIBLE:
        draft_status = ContestDraftStatus.BLOCKED
        title = "Chargeback Contest Response — BLOCKED"
        summary = (
            "The dispute is NOT ELIGIBLE for representment due to critical factual contradictions or policy disqualifications."
        )

        crit_findings = policy_db.critical_findings.get("findings", []) if policy_db and policy_db.critical_findings else []
        for finding in crit_findings:
            limitations.append(str(finding))
            review_flags.append(
                ReviewFlag(
                    flag_code="POLICY_DISQUALIFICATION",
                    severity="CRITICAL",
                    message=str(finding),
                    source_ids=[policy_db.id] if policy_db else [],
                )
            )

        # Factual summary of disqualifying conditions
        factual_arguments.append(
            FactualArgument(
                argument_id=next_arg_id(),
                heading="Disqualification Factual Notice",
                statement="Submitted evidence contradicts trusted transaction records under policy evaluation.",
                support_level="CONTRADICTED",
                source_match_result_ids=[m.id for m in match_results if m.status == MatchStatus.MISMATCH.value],
                source_evidence_ids=[d.id for d in documents],
                source_fact_names=[m.fact_name for m in match_results if m.status == MatchStatus.MISMATCH.value],
                explanation="Critical identity or monetary contradiction prevents safe automated representment.",
            )
        )

    # -------------------------------------------------------------
    # CASE TYPE B: REVIEW_REQUIRED (HUMAN_REVIEW) or DRAFT (ELIGIBLE)
    # -------------------------------------------------------------
    else:
        if policy_decision == PolicyDecision.HUMAN_REVIEW:
            draft_status = ContestDraftStatus.REVIEW_REQUIRED
            title = "Chargeback Contest Response — REVIEW REQUIRED"
            summary = (
                "The draft contains unverified, incomplete, or ambiguous evidence requiring merchant human review."
            )
        else:
            draft_status = ContestDraftStatus.DRAFT
            title = "Chargeback Dispute Evidence Response"
            summary = "The available evidence supports the transaction and associated fulfillment records."

        # --- Argument 1: Transaction Identity ---
        pay_matches = [m for m in match_results if m.fact_name == "payment_id"]
        if pay_matches and any(m.status == MatchStatus.MATCH.value for m in pay_matches):
            m_obj = next(m for m in pay_matches if m.status == MatchStatus.MATCH.value)
            factual_arguments.append(
                FactualArgument(
                    argument_id=next_arg_id(),
                    heading="Transaction Identity Verification",
                    statement=TEMPLATE_TRANSACTION_IDENTITY_MATCH.format(payment_id=dispute.payment_id),
                    support_level="VERIFIED",
                    source_match_result_ids=[m_obj.id],
                    source_evidence_ids=[m_obj.evidence_id] if m_obj.evidence_id else [],
                    source_fact_names=["payment_id"],
                    explanation=m_obj.explanation or "Payment ID verified against trusted record.",
                )
            )
        else:
            limitations.append("Payment ID verification was not confirmed across all evidence documents.")

        # --- Argument 2: Amount & Currency Verification ---
        amt_matches = [m for m in match_results if m.fact_name == "amount_minor"]
        curr_matches = [m for m in match_results if m.fact_name == "currency"]

        amt_match_obj = next((m for m in amt_matches if m.status == MatchStatus.MATCH.value), None)
        amt_mismatch_obj = next((m for m in amt_matches if m.status == MatchStatus.MISMATCH.value), None)

        if amt_match_obj:
            fmt_amt = format_amount_display(dispute.amount, dispute.currency)
            factual_arguments.append(
                FactualArgument(
                    argument_id=next_arg_id(),
                    heading="Transaction Amount Verification",
                    statement=TEMPLATE_AMOUNT_MATCH.format(formatted_amount=fmt_amt),
                    support_level="VERIFIED",
                    source_match_result_ids=[amt_match_obj.id],
                    source_evidence_ids=[amt_match_obj.evidence_id] if amt_match_obj.evidence_id else [],
                    source_fact_names=["amount_minor"],
                    explanation=amt_match_obj.explanation or "Invoice amount matches trusted dispute amount.",
                )
            )
        elif amt_mismatch_obj:
            exp_fmt = format_amount_display(dispute.amount, dispute.currency)
            obs_val = amt_mismatch_obj.observed_value or amt_mismatch_obj.normalized_observed_value
            obs_fmt = (
                format_amount_display(int(obs_val), dispute.currency)
                if obs_val and str(obs_val).isdigit()
                else str(obs_val)
            )

            factual_arguments.append(
                FactualArgument(
                    argument_id=next_arg_id(),
                    heading="Transaction Amount Discrepancy Notice",
                    statement=TEMPLATE_AMOUNT_MISMATCH.format(expected_amount=exp_fmt, observed_amount=obs_fmt),
                    support_level="CONTRADICTED",
                    source_match_result_ids=[amt_mismatch_obj.id],
                    source_evidence_ids=[amt_mismatch_obj.evidence_id] if amt_mismatch_obj.evidence_id else [],
                    source_fact_names=["amount_minor"],
                    explanation=amt_mismatch_obj.explanation or "Amount discrepancy flagged.",
                )
            )
            review_flags.append(
                ReviewFlag(
                    flag_code="AMOUNT_MISMATCH",
                    severity="HIGH",
                    message=f"Evidence amount ({obs_fmt}) differs from trusted dispute amount ({exp_fmt}).",
                    source_ids=[amt_mismatch_obj.id],
                )
            )
        else:
            limitations.append(TEMPLATE_MISSING_EVIDENCE_SAFE)
            review_flags.append(
                ReviewFlag(
                    flag_code="MISSING_EVIDENCE",
                    severity="MEDIUM",
                    message="Transaction amount fact missing from evidence documents.",
                    source_ids=[],
                )
            )

        # Currency Verification
        curr_match_obj = next((m for m in curr_matches if m.status == MatchStatus.MATCH.value), None)
        if curr_match_obj:
            factual_arguments.append(
                FactualArgument(
                    argument_id=next_arg_id(),
                    heading="Currency Verification",
                    statement=TEMPLATE_CURRENCY_MATCH.format(currency=dispute.currency),
                    support_level="VERIFIED",
                    source_match_result_ids=[curr_match_obj.id],
                    source_evidence_ids=[curr_match_obj.evidence_id] if curr_match_obj.evidence_id else [],
                    source_fact_names=["currency"],
                    explanation=curr_match_obj.explanation or "Currency code verified.",
                )
            )

        # --- Argument 3: Order ID Verification ---
        ord_matches = [m for m in match_results if m.fact_name == "order_id"]
        ord_match_obj = next((m for m in ord_matches if m.status == MatchStatus.MATCH.value), None)
        if ord_match_obj:
            factual_arguments.append(
                FactualArgument(
                    argument_id=next_arg_id(),
                    heading="Merchant Order Relationship",
                    statement=TEMPLATE_ORDER_ID_MATCH.format(
                        order_id=ord_match_obj.expected_value or ord_match_obj.observed_value or ""
                    ),
                    support_level="VERIFIED",
                    source_match_result_ids=[ord_match_obj.id],
                    source_evidence_ids=[ord_match_obj.evidence_id] if ord_match_obj.evidence_id else [],
                    source_fact_names=["order_id"],
                    explanation=ord_match_obj.explanation or "Order ID matches trusted order record.",
                )
            )

        # --- Argument 4: Logistics & Tracking Verification ---
        awb_matches = [m for m in match_results if m.fact_name == "awb_number"]
        awb_match_obj = next((m for m in awb_matches if m.status == MatchStatus.MATCH.value), None)
        if awb_match_obj:
            awb_val = awb_match_obj.observed_value or awb_match_obj.expected_value or ""
            factual_arguments.append(
                FactualArgument(
                    argument_id=next_arg_id(),
                    heading="Logistics & Shipment Tracking",
                    statement=TEMPLATE_TRACKING_MATCH.format(awb_number=awb_val),
                    support_level="VERIFIED",
                    source_match_result_ids=[awb_match_obj.id],
                    source_evidence_ids=[awb_match_obj.evidence_id] if awb_match_obj.evidence_id else [],
                    source_fact_names=["awb_number"],
                    explanation=awb_match_obj.explanation or "Tracking number verified.",
                )
            )

        # --- Argument 5: Delivery & Fulfillment Proof ---
        date_matches = [m for m in match_results if m.fact_name == "delivery_date"]
        date_match_obj = next((m for m in date_matches if m.status == MatchStatus.MATCH.value), None)
        if date_match_obj:
            deliv_date_str = date_match_obj.observed_value or date_match_obj.normalized_observed_value or ""
            factual_arguments.append(
                FactualArgument(
                    argument_id=next_arg_id(),
                    heading="Delivery Fulfillment Proof",
                    statement=TEMPLATE_DELIVERY_DATE_MATCH.format(delivery_date=deliv_date_str),
                    support_level="VERIFIED",
                    source_match_result_ids=[date_match_obj.id],
                    source_evidence_ids=[date_match_obj.evidence_id] if date_match_obj.evidence_id else [],
                    source_fact_names=["delivery_date"],
                    explanation=date_match_obj.explanation or "Delivery date verified and plausible.",
                )
            )

        # Check Signature
        sig_matches = [m for m in match_results if m.fact_name == "signature_present"]
        if any(m.status == MatchStatus.MATCH.value for m in sig_matches):
            sig_obj = next(m for m in sig_matches if m.status == MatchStatus.MATCH.value)
            factual_arguments.append(
                FactualArgument(
                    argument_id=next_arg_id(),
                    heading="Recipient Signature Verification",
                    statement=TEMPLATE_SIGNATURE_VERIFIED,
                    support_level="VERIFIED",
                    source_match_result_ids=[sig_obj.id],
                    source_evidence_ids=[sig_obj.evidence_id] if sig_obj.evidence_id else [],
                    source_fact_names=["signature_present"],
                    explanation="Recipient signature verified on proof of delivery.",
                )
            )

        # Check Cross-Document Conflicts & Ambiguities
        conflicts = [m for m in match_results if m.status == MatchStatus.CROSS_DOCUMENT_CONFLICT.value]
        if conflicts:
            for conf in conflicts:
                conflict_vals = conf.observed_value or conf.explanation or ""
                review_flags.append(
                    ReviewFlag(
                        flag_code="CROSS_DOCUMENT_CONFLICT",
                        severity="HIGH",
                        message=f"Conflicting values across documents for '{conf.fact_name}': {conflict_vals}",
                        source_ids=[conf.id],
                    )
                )

        # Check Prompt Injection Warnings
        for doc in documents:
            ext = getattr(doc, "extraction", None)
            if ext:
                raw_warnings = []
                if getattr(ext, "extraction_warnings", None):
                    if isinstance(ext.extraction_warnings, dict):
                        raw_warnings.extend(ext.extraction_warnings.get("warnings", []))
                    elif isinstance(ext.extraction_warnings, list):
                        raw_warnings.extend(ext.extraction_warnings)
                if getattr(ext, "extracted_data", None) and isinstance(ext.extracted_data, dict):
                    ext_data_warns = ext.extracted_data.get("extraction_warnings") or ext.extracted_data.get("warnings")
                    if isinstance(ext_data_warns, list):
                        raw_warnings.extend(ext_data_warns)
                    elif isinstance(ext_data_warns, str):
                        raw_warnings.append(ext_data_warns)

                for w in raw_warnings:
                    w_str = str(w).lower()
                    if any(k in w_str for k in ("injection", "override", "adversarial", "ignore instructions")):
                        review_flags.append(
                            ReviewFlag(
                                flag_code="PROMPT_INJECTION_DEFENSE",
                                severity="HIGH",
                                message=TEMPLATE_PROMPT_INJECTION_WARNING,
                                source_ids=[doc.id],
                            )
                        )
                        limitations.append("Adversarial text attempt quarantined in evidence payload.")

        if len(review_flags) > 0 and draft_status != ContestDraftStatus.BLOCKED:
            draft_status = ContestDraftStatus.REVIEW_REQUIRED
            title = "Chargeback Contest Response — REVIEW REQUIRED"
            summary = "The draft contains unverified, incomplete, or ambiguous evidence requiring merchant human review."

    # Financial Immutability Verification Assertion
    await db.refresh(dispute)
    assert dispute.payment_id == payment_id_before, "Financial safety invariant violated: payment_id mutated"
    assert dispute.amount == amount_before, "Financial safety invariant violated: amount mutated"
    assert dispute.currency == currency_before, "Financial safety invariant violated: currency mutated"

    gen_timestamp = datetime.utcnow()

    # Construct Dispute Context Snapshot
    dispute_context = {
        "payment_id": dispute.payment_id,
        "amount_minor": dispute.amount,
        "currency": dispute.currency,
        "formatted_amount": format_amount_display(dispute.amount, dispute.currency),
        "reason_code": dispute.reason_code,
        "status": dispute.status,
    }

    # Deterministic Input Fingerprinting via Shared Helper
    input_fingerprint = compute_contest_draft_input_fingerprint(
        dispute_id=dispute_id,
        payment_id=dispute.payment_id,
        amount=dispute.amount,
        currency=dispute.currency,
        policy_result_id=policy_db.id if policy_db else None,
        policy_version=policy_db.policy_version if policy_db else None,
        policy_outcome=policy_db.outcome if policy_db else None,
        match_results=match_results,
        documents=documents,
        generator_version=GENERATOR_VERSION,
        draft_version=DRAFT_VERSION,
    )

    # Delete Old Drafts for Dispute & Persist New ContestDraft Record
    del_stmt = select(ContestDraftModel).where(ContestDraftModel.dispute_id == dispute_id)
    old_drafts = await db.execute(del_stmt)
    for old_d in old_drafts.scalars().all():
        await db.delete(old_d)
    await db.commit()

    draft_db_record = ContestDraftModel(
        dispute_id=dispute_id,
        policy_result_id=policy_db.id if policy_db else None,
        status=draft_status.value,
        draft_version=DRAFT_VERSION,
        generator_version=GENERATOR_VERSION,
        title=title,
        summary=summary,
        dispute_context=dispute_context,
        factual_arguments={"arguments": [a.model_dump() for a in factual_arguments]},
        evidence_references={"references": [e.model_dump() for e in evidence_refs]},
        limitations={"limitations": limitations},
        review_flags={"flags": [f.model_dump() for f in review_flags]},
        input_fingerprint=input_fingerprint,
        created_at=gen_timestamp,
        updated_at=gen_timestamp,
    )
    db.add(draft_db_record)
    await db.commit()
    await db.refresh(draft_db_record)

    logger.info(
        f"AUDIT [Contest Draft Complete]: dispute_id={dispute_id}, draft_id={draft_db_record.id}, "
        f"status={draft_status.value}, generator_version={GENERATOR_VERSION}, fingerprint={input_fingerprint[:12]}..."
    )

    return ContestDraft(
        id=draft_db_record.id,
        dispute_id=dispute_id,
        policy_result_id=policy_db.id if policy_db else None,
        draft_version=DRAFT_VERSION,
        generator_version=GENERATOR_VERSION,
        status=draft_status,
        title=title,
        summary=summary,
        dispute_context=dispute_context,
        factual_arguments=factual_arguments,
        evidence_references=evidence_refs,
        limitations=limitations,
        review_flags=review_flags,
        input_fingerprint=input_fingerprint,
        generated_at=gen_timestamp,
    )
