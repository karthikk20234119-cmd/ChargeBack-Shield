"""
Deterministic Contest Response Templates — Chargeback Shield Task 5.1

Provides evidence-grounded templates for argument construction, currency formatting,
and discrepancy warnings. ZERO LLM calls. ZERO fact fabrication.
"""

from typing import Any, Optional


def format_amount_display(amount_minor: Optional[int], currency: Optional[str] = "INR") -> str:
    """
    Renders integer minor units (paise/cents) into human-readable currency string.
    Only formats symbol when currency is known. Performs ZERO currency conversion.
    """
    if amount_minor is None:
        return "Unknown Amount"

    curr_clean = (currency or "INR").strip().upper()
    major_units = amount_minor / 100.0

    if curr_clean == "INR":
        return f"₹{major_units:,.2f}"
    elif curr_clean == "USD":
        return f"${major_units:,.2f}"
    elif curr_clean == "EUR":
        return f"€{major_units:,.2f}"
    else:
        return f"{curr_clean} {major_units:,.2f}"


# --- Template Strings ---

TEMPLATE_TRANSACTION_IDENTITY_MATCH = (
    "The payment transaction identity '{payment_id}' in the submitted evidence matches "
    "the trusted transaction record."
)

TEMPLATE_AMOUNT_MATCH = (
    "The transaction amount in the submitted evidence matches the trusted dispute amount of {formatted_amount}."
)

TEMPLATE_AMOUNT_MISMATCH = (
    "The evidence contains a transaction amount of {observed_amount} which differs from "
    "the trusted dispute amount of {expected_amount}. Human review is required."
)

TEMPLATE_CURRENCY_MATCH = (
    "The currency code in the evidence matches the trusted dispute currency '{currency}'."
)

TEMPLATE_CURRENCY_MISMATCH = (
    "The evidence currency code '{observed_currency}' differs from trusted dispute currency '{expected_currency}'. "
    "Human review is required."
)

TEMPLATE_ORDER_ID_MATCH = (
    "The order reference '{order_id}' in the evidence matches the trusted merchant order record."
)

TEMPLATE_ORDER_ID_MISMATCH = (
    "The order reference '{observed_order_id}' in the evidence differs from expected merchant order '{expected_order_id}'."
)

TEMPLATE_TRACKING_MATCH = (
    "Logistics evidence establishes shipment tracking number (AWB) '{awb_number}' registered with the carrier."
)

TEMPLATE_TRACKING_MISMATCH = (
    "Logistics evidence tracking number '{observed_awb}' differs from expected tracking number '{expected_awb}'."
)

TEMPLATE_DELIVERY_DATE_MATCH = (
    "Delivery proof documents successful fulfillment completed on {delivery_date}."
)

TEMPLATE_DELIVERY_DATE_INVALID = (
    "The evidence delivery date '{delivery_date}' is invalid or temporally improbable relative to dispute timeline."
)

TEMPLATE_SIGNATURE_VERIFIED = (
    "Recipient signature was verified on the proof of delivery document."
)

TEMPLATE_MISSING_EVIDENCE_SAFE = (
    "Supporting evidence was not available for this field."
)

TEMPLATE_CROSS_DOCUMENT_CONFLICT = (
    "Multiple conflicting values ({conflict_values}) were identified across evidence documents "
    "and could not be reconciled deterministically."
)

TEMPLATE_UNVERIFIABLE_FIELD = (
    "Extraction confidence for '{field_name}' ({confidence_score}) is below the required verification threshold."
)

TEMPLATE_PROMPT_INJECTION_WARNING = (
    "Adversarial text or prompt injection attempt detected in raw document payload. "
    "Raw text claims have been safely quarantined."
)
