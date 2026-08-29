"""
Deterministic Evidence Matching Engine — Phase 4 Task 4.2

Compares trusted dispute/payment data against ExtractedEvidence facts.
Produces deterministic, explainable MatchResult records with full provenance,
confidence tracking, and historical snapshot values.

FINANCIAL & SAFETY INVARIANTS:
- MUST NOT modify trusted dispute payment_id, amount, or currency
- MUST NOT evaluate policy rules or decide eligibility (ELIGIBLE, HUMAN_REVIEW, NOT_ELIGIBLE)
- MUST NOT generate contest responses or mutate Razorpay
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.matching import MatchResult
from backend.app.models.processed_artifact import ProcessedArtifact
from backend.app.schemas.matching import (
    DisputeMatchSummary,
    FieldMatchDetail,
    MatchResultSchema,
    MatchStatus,
    MatchingRunResult,
)
from backend.app.utils.normalization import (
    normalize_amount,
    normalize_confidence,
    normalize_date,
    normalize_email,
    normalize_phone,
    normalize_tracking_id,
)

logger = logging.getLogger(__name__)

MATCHER_VERSION = "1.0"


# ===========================================================================
# NORMALIZATION & COMPARISON HELPERS
# ===========================================================================


def normalize_identifier(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    clean = str(val).strip().lower()
    clean = re.sub(r"^[#:]+", "", clean)
    return clean if clean else None


def normalize_currency(val: Optional[str]) -> Optional[str]:
    if not val:
        return "INR"
    return str(val).strip().upper()


def normalize_name(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    clean = re.sub(r"\s+", " ", str(val).strip().lower())
    return clean if clean else None


def parse_iso_date(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d")
    except Exception:
        return None


def compare_exact(expected: Optional[str], observed: Optional[str]) -> Tuple[MatchStatus, Optional[str], str]:
    """Compares exact string identifiers."""
    if expected is None and observed is None:
        return MatchStatus.NOT_COMPARABLE, None, "Both expected and observed values are empty"
    if expected is not None and observed is None:
        return MatchStatus.MISSING, None, f"Expected value '{expected}' missing from evidence"
    if expected is None and observed is not None:
        return MatchStatus.NOT_COMPARABLE, str(observed).strip(), f"Observed value '{observed}' has no trusted reference"

    exp_clean = str(expected).strip()
    obs_clean = str(observed).strip()

    if exp_clean == obs_clean:
        return MatchStatus.MATCH, obs_clean, f"Exact match: '{exp_clean}'"
    return MatchStatus.MISMATCH, obs_clean, f"Mismatch: expected '{exp_clean}', observed '{obs_clean}'"


def compare_amount(expected_minor: Optional[int], observed_val: Any) -> Tuple[MatchStatus, Optional[str], str]:
    """
    Compares currency amounts strictly using normalized integer minor units (paise/cents).
    Never uses floating-point equality or raw currency strings.
    """
    if expected_minor is None:
        return MatchStatus.NOT_COMPARABLE, None, "Trusted amount is not available"

    if observed_val is None:
        return MatchStatus.MISSING, None, f"Amount missing from evidence (expected {expected_minor} paise)"

    obs_minor = normalize_amount(observed_val)
    if obs_minor is None:
        return MatchStatus.AMBIGUOUS, None, f"Unparseable amount value in evidence: '{observed_val}'"

    obs_str = str(obs_minor)
    if expected_minor == obs_minor:
        return MatchStatus.MATCH, obs_str, f"Amount matches trusted dispute amount: {expected_minor} paise"

    return (
        MatchStatus.MISMATCH,
        obs_str,
        f"Amount mismatch: trusted dispute amount is {expected_minor} paise, evidence amount is {obs_minor} paise",
    )


def compare_currency(expected_code: Optional[str], observed_code: Optional[str]) -> Tuple[MatchStatus, Optional[str], str]:
    """Compares uppercase ISO currency codes."""
    exp_norm = (expected_code or "INR").strip().upper()
    if not observed_code:
        return MatchStatus.MISSING, None, f"Currency code missing from evidence (expected {exp_norm})"

    obs_norm = str(observed_code).strip().upper()
    if exp_norm == obs_norm:
        return MatchStatus.MATCH, obs_norm, f"Currency matches trusted code: '{exp_norm}'"

    return MatchStatus.MISMATCH, obs_norm, f"Currency mismatch: expected '{exp_norm}', observed '{obs_norm}'"


def compare_date(expected_date: Optional[str], observed_date: Optional[str]) -> Tuple[MatchStatus, Optional[str], str]:
    """Compares normalized ISO date strings (YYYY-MM-DD)."""
    if not expected_date and not observed_date:
        return MatchStatus.NOT_COMPARABLE, None, "No date specified in reference or evidence"
    if expected_date and not observed_date:
        return MatchStatus.MISSING, None, f"Date missing from evidence (expected {expected_date})"

    obs_norm = normalize_date(observed_date)
    if not obs_norm:
        return MatchStatus.AMBIGUOUS, None, f"Partial or unparseable date in evidence: '{observed_date}'"

    if not expected_date:
        return MatchStatus.NOT_COMPARABLE, obs_norm, f"Evidence date '{obs_norm}' has no expected reference date"

    exp_norm = normalize_date(expected_date) or expected_date.strip()

    if exp_norm == obs_norm:
        return MatchStatus.MATCH, obs_norm, f"Date matches expected date: '{exp_norm}'"
    return MatchStatus.MISMATCH, obs_norm, f"Date mismatch: expected '{exp_norm}', observed '{obs_norm}'"


def compare_email(expected_email: Optional[str], observed_email: Optional[str]) -> Tuple[MatchStatus, Optional[str], str]:
    """Compares emails using normalize_email."""
    if not expected_email and not observed_email:
        return MatchStatus.NOT_COMPARABLE, None, "No email specified"
    if expected_email and not observed_email:
        return MatchStatus.MISSING, None, f"Email missing from evidence (expected {expected_email})"

    obs_norm = normalize_email(observed_email)
    if not obs_norm:
        return MatchStatus.AMBIGUOUS, None, f"Invalid email format in evidence: '{observed_email}'"

    if not expected_email:
        return MatchStatus.NOT_COMPARABLE, obs_norm, f"Evidence email '{obs_norm}' has no expected reference"

    exp_norm = normalize_email(expected_email) or expected_email.strip().lower()
    if exp_norm == obs_norm:
        return MatchStatus.MATCH, obs_norm, f"Email matches expected address: '{exp_norm}'"
    return MatchStatus.MISMATCH, obs_norm, f"Email mismatch: expected '{exp_norm}', observed '{obs_norm}'"


def compare_phone(expected_phone: Optional[str], observed_phone: Optional[str]) -> Tuple[MatchStatus, Optional[str], str]:
    """Compares phone numbers using normalize_phone."""
    if not expected_phone and not observed_phone:
        return MatchStatus.NOT_COMPARABLE, None, "No phone specified"
    if expected_phone and not observed_phone:
        return MatchStatus.MISSING, None, f"Phone missing from evidence (expected {expected_phone})"

    obs_norm = normalize_phone(observed_phone)
    if not obs_norm:
        return MatchStatus.AMBIGUOUS, None, f"Unparseable phone formatting in evidence: '{observed_phone}'"

    if not expected_phone:
        return MatchStatus.NOT_COMPARABLE, obs_norm, f"Evidence phone '{obs_norm}' has no expected reference"

    exp_norm = normalize_phone(expected_phone) or expected_phone.strip()
    if exp_norm == obs_norm:
        return MatchStatus.MATCH, obs_norm, f"Phone matches expected number: '{exp_norm}'"
    return MatchStatus.MISMATCH, obs_norm, f"Phone mismatch: expected '{exp_norm}', observed '{obs_norm}'"


def compare_tracking_id(expected_awb: Optional[str], observed_awb: Optional[str]) -> Tuple[MatchStatus, Optional[str], str]:
    """Compares shipment tracking numbers using normalize_tracking_id."""
    if not expected_awb and not observed_awb:
        return MatchStatus.NOT_COMPARABLE, None, "No tracking ID specified"
    if expected_awb and not observed_awb:
        return MatchStatus.MISSING, None, f"Tracking ID missing from evidence (expected {expected_awb})"

    obs_norm = normalize_tracking_id(observed_awb)
    if not obs_norm:
        return MatchStatus.AMBIGUOUS, None, f"Unparseable tracking number in evidence: '{observed_awb}'"

    if not expected_awb:
        return MatchStatus.NOT_COMPARABLE, obs_norm, f"Evidence tracking ID '{obs_norm}' has no trusted reference"

    exp_norm = normalize_tracking_id(expected_awb) or expected_awb.strip().upper()
    if exp_norm == obs_norm:
        return MatchStatus.MATCH, obs_norm, f"Tracking ID matches expected number: '{exp_norm}'"
    return MatchStatus.MISMATCH, obs_norm, f"Tracking ID mismatch: expected '{exp_norm}', observed '{obs_norm}'"


# ===========================================================================
# MATCHING ENGINE CORE SERVICES
# ===========================================================================


async def run_dispute_matching(
    dispute_id: str,
    db: AsyncSession,
    reference_date: str = "2026-08-26",
) -> DisputeMatchSummary:
    """
    Executes deterministic evidence matching comparing extracted evidence facts
    against trusted dispute data. Pure deterministic logic (zero LLM/embeddings).
    """
    # 1. Fetch Dispute Record with Documents and Extractions
    stmt = (
        select(Dispute)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Dispute.documents).selectinload(EvidenceDocument.extraction),
            selectinload(Dispute.documents).selectinload(EvidenceDocument.artifacts),
        )
        .where(Dispute.id == dispute_id)
    )

    res = await db.execute(stmt)
    dispute = res.scalar_one_or_none()

    if not dispute:
        raise ValueError(f"Dispute with ID '{dispute_id}' not found.")

    # Financial Safety Assertion: Capture trusted identity
    trusted_payment_id = dispute.payment_id
    trusted_amount_minor = dispute.amount
    trusted_currency = normalize_currency(dispute.currency)

    ref_dt = parse_iso_date(reference_date) or datetime(2026, 8, 26)

    raw_payload = dispute.raw_payload or {}
    dispute_entity = raw_payload.get("payload", {}).get("dispute", {}).get("entity", {})
    trusted_order_id = dispute_entity.get("order_id") or raw_payload.get("order_id")
    trusted_customer_name = dispute.customer_email or dispute_entity.get("customer_name")
    trusted_awb = dispute_entity.get("awb_number") or raw_payload.get("awb_number")

    field_results: List[FieldMatchDetail] = []

    # Track cross-document extractions
    extracted_order_ids: Dict[str, List[str]] = {}
    extracted_awbs: Dict[str, List[str]] = {}
    shipment_dates: List[datetime] = []

    stmt_docs = (
        select(EvidenceDocument)
        .options(
            selectinload(EvidenceDocument.extraction),
            selectinload(EvidenceDocument.artifacts),
        )
        .where(EvidenceDocument.dispute_id == dispute_id)
    )
    res_docs = await db.execute(stmt_docs)
    documents = res_docs.scalars().all()

    for doc in documents:
        if not doc.extraction or doc.processing_status != "AI_EXTRACTED":
            continue

        ext: ExtractedEvidence = doc.extraction
        doc_type = (ext.document_type or "general").lower()
        ev_id = doc.id
        conf_map = ext.confidence_by_field or {}

        # --- A. Payment ID (Critical) ---
        if doc_type == "invoice":
            norm_exp_pay = normalize_identifier(trusted_payment_id)
            norm_ext_pay = normalize_identifier(ext.payment_id)
            if not ext.payment_id:
                field_results.append(
                    FieldMatchDetail(
                        field="payment_id",
                        expected_value=trusted_payment_id,
                        extracted_value=ext.payment_id,
                        normalized_expected=norm_exp_pay,
                        normalized_extracted=norm_ext_pay,
                        status=MatchStatus.MISSING,
                        is_critical=True,
                        reason="Payment ID is missing from invoice",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )
            elif norm_exp_pay == norm_ext_pay:
                field_results.append(
                    FieldMatchDetail(
                        field="payment_id",
                        expected_value=trusted_payment_id,
                        extracted_value=ext.payment_id,
                        normalized_expected=norm_exp_pay,
                        normalized_extracted=norm_ext_pay,
                        status=MatchStatus.MATCH,
                        is_critical=True,
                        reason="Payment ID matches trusted transaction record",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )
            else:
                field_results.append(
                    FieldMatchDetail(
                        field="payment_id",
                        expected_value=trusted_payment_id,
                        extracted_value=ext.payment_id,
                        normalized_expected=norm_exp_pay,
                        normalized_extracted=norm_ext_pay,
                        status=MatchStatus.MISMATCH,
                        is_critical=True,
                        reason="Payment ID does not match trusted transaction record",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )

        # --- B. Order ID (Critical) ---
        if doc_type in {"invoice", "shipping_proof", "delivery_proof"}:
            if ext.order_id:
                norm_ord = normalize_identifier(ext.order_id)
                if norm_ord:
                    extracted_order_ids.setdefault(norm_ord, []).append(ev_id)

            if trusted_order_id:
                norm_exp_ord = normalize_identifier(trusted_order_id)
                norm_ext_ord = normalize_identifier(ext.order_id)
                if not ext.order_id:
                    field_results.append(
                        FieldMatchDetail(
                            field="order_id",
                            expected_value=trusted_order_id,
                            extracted_value=ext.order_id,
                            normalized_expected=norm_exp_ord,
                            normalized_extracted=norm_ext_ord,
                            status=MatchStatus.MISSING,
                            is_critical=True,
                            reason=f"Order ID missing from {doc_type}",
                            source_doc_type=doc_type,
                            evidence_id=ev_id,
                        )
                    )
                elif norm_exp_ord == norm_ext_ord:
                    field_results.append(
                        FieldMatchDetail(
                            field="order_id",
                            expected_value=trusted_order_id,
                            extracted_value=ext.order_id,
                            normalized_expected=norm_exp_ord,
                            normalized_extracted=norm_ext_ord,
                            status=MatchStatus.MATCH,
                            is_critical=True,
                            reason=f"Order ID matches trusted order record in {doc_type}",
                            source_doc_type=doc_type,
                            evidence_id=ev_id,
                        )
                    )
                else:
                    field_results.append(
                        FieldMatchDetail(
                            field="order_id",
                            expected_value=trusted_order_id,
                            extracted_value=ext.order_id,
                            normalized_expected=norm_exp_ord,
                            normalized_extracted=norm_ext_ord,
                            status=MatchStatus.MISMATCH,
                            is_critical=True,
                            reason=f"Order ID mismatch in {doc_type}",
                            source_doc_type=doc_type,
                            evidence_id=ev_id,
                        )
                    )

        # --- C. Amount Minor (Critical) ---
        if doc_type == "invoice":
            if ext.amount_minor is None:
                field_results.append(
                    FieldMatchDetail(
                        field="amount_minor",
                        expected_value=trusted_amount_minor,
                        extracted_value=ext.amount_minor,
                        normalized_expected=str(trusted_amount_minor),
                        normalized_extracted=None,
                        status=MatchStatus.MISSING,
                        is_critical=True,
                        reason="Invoice amount is missing",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )
            elif trusted_amount_minor == ext.amount_minor:
                field_results.append(
                    FieldMatchDetail(
                        field="amount_minor",
                        expected_value=trusted_amount_minor,
                        extracted_value=ext.amount_minor,
                        normalized_expected=str(trusted_amount_minor),
                        normalized_extracted=str(ext.amount_minor),
                        status=MatchStatus.MATCH,
                        is_critical=True,
                        reason="Invoice amount matches trusted dispute amount",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )
            else:
                field_results.append(
                    FieldMatchDetail(
                        field="amount_minor",
                        expected_value=trusted_amount_minor,
                        extracted_value=ext.amount_minor,
                        normalized_expected=str(trusted_amount_minor),
                        normalized_extracted=str(ext.amount_minor),
                        status=MatchStatus.MISMATCH,
                        is_critical=True,
                        reason="Invoice amount mismatch against dispute amount",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )

        # --- D. Currency (Critical) ---
        if doc_type == "invoice":
            norm_exp_curr = normalize_currency(trusted_currency)
            norm_ext_curr = normalize_currency(ext.currency)
            if not ext.currency:
                field_results.append(
                    FieldMatchDetail(
                        field="currency",
                        expected_value=trusted_currency,
                        extracted_value=ext.currency,
                        normalized_expected=norm_exp_curr,
                        normalized_extracted=norm_ext_curr,
                        status=MatchStatus.UNVERIFIABLE,
                        is_critical=True,
                        reason="Currency missing from invoice",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )
            elif norm_exp_curr == norm_ext_curr:
                field_results.append(
                    FieldMatchDetail(
                        field="currency",
                        expected_value=trusted_currency,
                        extracted_value=ext.currency,
                        normalized_expected=norm_exp_curr,
                        normalized_extracted=norm_ext_curr,
                        status=MatchStatus.MATCH,
                        is_critical=True,
                        reason="Currency matches trusted currency",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )
            else:
                field_results.append(
                    FieldMatchDetail(
                        field="currency",
                        expected_value=trusted_currency,
                        extracted_value=ext.currency,
                        normalized_expected=norm_exp_curr,
                        normalized_extracted=norm_ext_curr,
                        status=MatchStatus.MISMATCH,
                        is_critical=True,
                        reason="Currency mismatch",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )

        # --- E. Airway Bill (AWB) ---
        if doc_type in {"shipping_proof", "delivery_proof"}:
            if ext.awb_number:
                norm_awb = normalize_identifier(ext.awb_number)
                if norm_awb:
                    extracted_awbs.setdefault(norm_awb, []).append(ev_id)

            if not ext.awb_number:
                field_results.append(
                    FieldMatchDetail(
                        field="awb_number",
                        expected_value=trusted_awb,
                        extracted_value=ext.awb_number,
                        normalized_expected=normalize_identifier(trusted_awb) if trusted_awb else None,
                        normalized_extracted=None,
                        status=MatchStatus.MISSING,
                        is_critical=True,
                        reason=f"AWB number missing from {doc_type}",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )
            elif trusted_awb:
                norm_exp_awb = normalize_identifier(trusted_awb)
                norm_ext_awb = normalize_identifier(ext.awb_number)
                if norm_exp_awb == norm_ext_awb:
                    field_results.append(
                        FieldMatchDetail(
                            field="awb_number",
                            expected_value=trusted_awb,
                            extracted_value=ext.awb_number,
                            normalized_expected=norm_exp_awb,
                            normalized_extracted=norm_ext_awb,
                            status=MatchStatus.MATCH,
                            is_critical=True,
                            reason=f"AWB number matches trusted dispute AWB in {doc_type}",
                            source_doc_type=doc_type,
                            evidence_id=ev_id,
                        )
                    )
                else:
                    field_results.append(
                        FieldMatchDetail(
                            field="awb_number",
                            expected_value=trusted_awb,
                            extracted_value=ext.awb_number,
                            normalized_expected=norm_exp_awb,
                            normalized_extracted=norm_ext_awb,
                            status=MatchStatus.MISMATCH,
                            is_critical=True,
                            reason=f"AWB number mismatch in {doc_type}",
                            source_doc_type=doc_type,
                            evidence_id=ev_id,
                        )
                    )

        # Track shipment date for temporal validation
        if doc_type == "shipping_proof" and ext.delivery_date:
            ship_dt = parse_iso_date(ext.delivery_date)
            if ship_dt:
                shipment_dates.append(ship_dt)

        # --- F. Delivery Date Temporal Checks ---
        if doc_type == "delivery_proof":
            if not ext.delivery_date:
                field_results.append(
                    FieldMatchDetail(
                        field="delivery_date",
                        expected_value="Valid past date",
                        extracted_value=None,
                        status=MatchStatus.MISSING,
                        is_critical=False,
                        reason="Delivery date missing from delivery proof",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )
            else:
                deliv_dt = parse_iso_date(ext.delivery_date)
                if not deliv_dt:
                    field_results.append(
                        FieldMatchDetail(
                            field="delivery_date",
                            expected_value="Valid past ISO date",
                            extracted_value=ext.delivery_date,
                            status=MatchStatus.UNVERIFIABLE,
                            is_critical=False,
                            reason="Delivery date format is invalid or unparseable",
                            source_doc_type=doc_type,
                            evidence_id=ev_id,
                        )
                    )
                elif deliv_dt > ref_dt:
                    field_results.append(
                        FieldMatchDetail(
                            field="delivery_date",
                            expected_value=f"<= {reference_date}",
                            extracted_value=ext.delivery_date,
                            normalized_expected=reference_date,
                            normalized_extracted=ext.delivery_date,
                            status=MatchStatus.MISMATCH,
                            is_critical=True,
                            reason="Delivery date is in the future relative to evaluation reference date",
                            source_doc_type=doc_type,
                            evidence_id=ev_id,
                        )
                    )
                elif shipment_dates and any(deliv_dt < s_dt for s_dt in shipment_dates):
                    field_results.append(
                        FieldMatchDetail(
                            field="delivery_date",
                            expected_value=">= shipment_date",
                            extracted_value=ext.delivery_date,
                            status=MatchStatus.MISMATCH,
                            is_critical=True,
                            reason="Delivery date is earlier than shipment date",
                            source_doc_type=doc_type,
                            evidence_id=ev_id,
                        )
                    )
                else:
                    field_results.append(
                        FieldMatchDetail(
                            field="delivery_date",
                            expected_value=f"<= {reference_date}",
                            extracted_value=ext.delivery_date,
                            normalized_expected=reference_date,
                            normalized_extracted=ext.delivery_date,
                            status=MatchStatus.MATCH,
                            is_critical=False,
                            reason="Delivery date is valid and temporally plausible",
                            source_doc_type=doc_type,
                            evidence_id=ev_id,
                        )
                    )

        # --- H. Recipient Signature Verification ---
        if doc_type == "delivery_proof":
            if ext.signature_present is None or ext.signature_present is False:
                field_results.append(
                    FieldMatchDetail(
                        field="signature_present",
                        expected_value="True",
                        extracted_value=str(ext.signature_present),
                        status=MatchStatus.UNVERIFIABLE if ext.signature_present is None else MatchStatus.MISSING,
                        is_critical=False,
                        reason="Recipient signature is unverified or missing from delivery proof",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )

        # --- I. Field Extraction Confidence Threshold ---
        for f_name, score in conf_map.items():
            if isinstance(score, (int, float)) and score < 0.70:
                field_results.append(
                    FieldMatchDetail(
                        field=f_name,
                        expected_value=">= 0.70 confidence",
                        extracted_value=str(score),
                        status=MatchStatus.UNVERIFIABLE,
                        is_critical=(f_name in {"order_id", "payment_id", "amount_minor"}),
                        reason=f"Extraction confidence for {f_name} ({score}) is below required 0.70 threshold",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )

        # --- G. Customer Name ---
        if trusted_customer_name and ext.customer_name:
            norm_exp_name = normalize_name(trusted_customer_name)
            norm_ext_name = normalize_name(ext.customer_name)
            if norm_exp_name and norm_ext_name and (norm_exp_name in norm_ext_name or norm_ext_name in norm_exp_name):
                field_results.append(
                    FieldMatchDetail(
                        field="customer_name",
                        expected_value=trusted_customer_name,
                        extracted_value=ext.customer_name,
                        normalized_expected=norm_exp_name,
                        normalized_extracted=norm_ext_name,
                        status=MatchStatus.MATCH,
                        is_critical=False,
                        reason="Customer name matches trusted record",
                        source_doc_type=doc_type,
                        evidence_id=ev_id,
                    )
                )

    # 4. Cross-Document Contradiction Checks
    if len(extracted_order_ids) > 1:
        keys_str = ", ".join(extracted_order_ids.keys())
        field_results.append(
            FieldMatchDetail(
                field="order_id",
                expected_value="Consistent order ID across documents",
                extracted_value=keys_str,
                status=MatchStatus.CROSS_DOCUMENT_CONFLICT,
                is_critical=True,
                reason=f"Conflicting Order IDs detected across documents: {keys_str}",
                source_doc_type="cross_document",
            )
        )

    if len(extracted_awbs) > 1:
        keys_str = ", ".join(extracted_awbs.keys())
        field_results.append(
            FieldMatchDetail(
                field="awb_number",
                expected_value="Consistent AWB across documents",
                extracted_value=keys_str,
                status=MatchStatus.CROSS_DOCUMENT_CONFLICT,
                is_critical=True,
                reason=f"Conflicting Airway Bills (AWB) detected across documents: {keys_str}",
                source_doc_type="cross_document",
            )
        )

    # 5. Calculate Summary Totals
    matches_cnt = sum(1 for f in field_results if f.status == MatchStatus.MATCH)
    mismatches_cnt = sum(1 for f in field_results if f.status == MatchStatus.MISMATCH)
    missing_cnt = sum(1 for f in field_results if f.status == MatchStatus.MISSING)
    unverifiable_cnt = sum(1 for f in field_results if f.status == MatchStatus.UNVERIFIABLE)
    conflicts_cnt = sum(1 for f in field_results if f.status == MatchStatus.CROSS_DOCUMENT_CONFLICT)

    has_critical_mismatch = any(
        f.is_critical and f.status in {MatchStatus.MISMATCH, MatchStatus.CROSS_DOCUMENT_CONFLICT}
        for f in field_results
    )

    if conflicts_cnt > 0:
        overall_status = "CONFLICT_DETECTED"
    elif has_critical_mismatch:
        overall_status = "CRITICAL_MISMATCH"
    elif mismatches_cnt > 0:
        overall_status = "MISMATCH_DETECTED"
    elif missing_cnt > 0 or unverifiable_cnt > 0:
        overall_status = "INCOMPLETE_EVIDENCE"
    elif matches_cnt > 0:
        overall_status = "DETERMINISTIC_MATCH"
    else:
        overall_status = "NO_EXTRACTION_DATA"

    # 6. Delete Old Match Results & Persist New Results
    del_stmt = select(MatchResult).where(MatchResult.dispute_id == dispute_id)
    old_res = await db.execute(del_stmt)
    for old_row in old_res.scalars().all():
        await db.delete(old_row)
    await db.commit()

    for item in field_results:
        db_match = MatchResult(
            dispute_id=dispute_id,
            evidence_id=item.evidence_id,
            field=item.field,
            fact_name=item.field,
            expected_value=str(item.expected_value) if item.expected_value is not None else None,
            extracted_value=str(item.extracted_value) if item.extracted_value is not None else None,
            observed_value=str(item.extracted_value) if item.extracted_value is not None else None,
            normalized_expected=item.normalized_expected,
            normalized_expected_value=item.normalized_expected,
            normalized_extracted=item.normalized_extracted,
            normalized_observed_value=item.normalized_extracted,
            status=item.status.value,
            is_critical=item.is_critical,
            explanation=item.reason,
            reason=item.reason,
            source=item.source_doc_type,
        )
        db.add(db_match)

    await db.commit()

    # Financial Safety Assertion
    await db.refresh(dispute)
    assert dispute.payment_id == trusted_payment_id, "Financial safety invariant violated: payment_id mutated"
    assert dispute.amount == trusted_amount_minor, "Financial safety invariant violated: amount mutated"

    return DisputeMatchSummary(
        dispute_id=dispute_id,
        overall_status=overall_status,
        has_critical_mismatch=has_critical_mismatch,
        total_fields_evaluated=len(field_results),
        matches_count=matches_cnt,
        mismatches_count=mismatches_cnt,
        missing_count=missing_cnt,
        unverifiable_count=unverifiable_cnt,
        conflicts_count=conflicts_cnt,
        field_results=field_results,
    )


async def run_evidence_matching(
    dispute_id: str,
    db: AsyncSession,
) -> MatchingRunResult:
    """
    Task 4.2 Entrypoint: Executes deterministic evidence matching comparing trusted dispute facts
    against all ExtractedEvidence document facts for a dispute.
    Returns typed MatchingRunResult.
    """
    summary = await run_dispute_matching(dispute_id, db)

    results: List[MatchResultSchema] = [
        MatchResultSchema(
            dispute_id=dispute_id,
            evidence_id=detail.evidence_id,
            processed_artifact_id=None,
            fact_name=detail.field,
            expected_value=str(detail.expected_value) if detail.expected_value is not None else None,
            observed_value=str(detail.extracted_value) if detail.extracted_value is not None else None,
            normalized_expected_value=detail.normalized_expected,
            normalized_observed_value=detail.normalized_extracted,
            status=detail.status,
            confidence="HIGH" if detail.status == MatchStatus.MATCH else "MEDIUM",
            source_page=1,
            extraction_method="vision",
            matcher_version=MATCHER_VERSION,
            explanation=detail.reason,
        )
        for detail in summary.field_results
    ]

    return MatchingRunResult(
        dispute_id=dispute_id,
        status=summary.overall_status,
        total_facts=summary.total_fields_evaluated,
        match_count=summary.matches_count,
        mismatches_count=summary.mismatches_count,
        missing_count=summary.missing_count,
        ambiguous_count=summary.unverifiable_count,
        results=results,
    )
