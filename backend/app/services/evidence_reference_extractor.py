"""
Razorpay Evidence Reference Extractor — Task 3.3A

Extracts and validates evidence document references from Razorpay dispute
evidence payloads into typed EvidenceReference models.

SECURITY & SAFETY GUARANTEES:
- Strictly read-only data extraction
- Path traversal & injection defense on document IDs
- Deduplicates document IDs while preserving all associated categories
- Malformed inputs generate structured warnings/invalid_items without crashing
- Zero file system / zero network side effects
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.app.schemas.evidence_reference import (
    EvidenceReference,
    EvidenceReferenceExtractionResult,
    EvidenceReferenceInvalidItem,
)
from backend.app.schemas.razorpay import RazorpayDisputeResponse

logger = logging.getLogger(__name__)

# Official supported Razorpay evidence categories
SUPPORTED_EVIDENCE_CATEGORIES = {
    "shipping_proof",
    "billing_proof",
    "cancellation_proof",
    "customer_communication",
    "proof_of_service",
    "explanation_letter",
    "refund_confirmation",
    "access_activity_log",
    "refund_cancellation_policy",
    "term_and_conditions",
    "terms_conditions",  # Supported alias
    "others",
}


def validate_document_id(doc_id_raw: Any) -> tuple[str | None, str | None]:
    """
    Validates a raw document ID.

    Security checks:
    - Must be a non-boolean string
    - Must be non-empty after trimming whitespace
    - Maximum length: 64 characters
    - Must NOT contain path traversal / injection characters ('/', '\\', '..', ':', null bytes)
    - Must match alphanumeric identifier pattern ^[a-zA-Z0-9_-]+$

    Returns:
        (valid_doc_id, None) if valid.
        (None, error_reason) if invalid.
    """
    if doc_id_raw is None:
        return None, "Document ID is None"

    if isinstance(doc_id_raw, bool) or not isinstance(doc_id_raw, str):
        return None, f"Document ID must be a string, got {type(doc_id_raw).__name__}"

    stripped = doc_id_raw.strip()
    if not stripped:
        return None, "Document ID is empty or whitespace only"

    if len(stripped) > 64:
        return None, f"Document ID exceeds maximum length of 64 characters (length: {len(stripped)})"

    # Path traversal & injection protection
    forbidden_chars = {"/", "\\", ":", "\x00"}
    if any(c in stripped for c in forbidden_chars) or ".." in stripped or "%00" in stripped:
        return None, f"Document ID contains path-like or unsafe characters: '{stripped}'"

    if not re.match(r"^[a-zA-Z0-9_-]+$", stripped):
        return None, f"Document ID contains invalid characters: '{stripped}'"

    return stripped, None


def extract_evidence_references(
    payload: Any,
    source_dispute_id: str | None = None,
) -> EvidenceReferenceExtractionResult:
    """
    Extracts evidence document references from a Razorpay dispute payload or evidence dict.

    Args:
        payload: RazorpayDisputeResponse, full dispute dict, or evidence dict.
        source_dispute_id: Optional dispute ID override.

    Returns:
        EvidenceReferenceExtractionResult containing references, warnings, and invalid_items.
    """
    result = EvidenceReferenceExtractionResult()
    ref_map: dict[str, EvidenceReference] = {}

    if payload is None:
        result.warnings.append("Evidence payload is None")
        return result

    dispute_id = source_dispute_id
    evidence_dict: dict[str, Any] | None = None

    # Handle input types
    if isinstance(payload, RazorpayDisputeResponse):
        dispute_id = dispute_id or payload.id
        # Check if raw dump contains evidence dict
        raw_dump = payload.model_dump()
        evidence_dict = raw_dump.get("evidence")
    elif isinstance(payload, dict):
        if "id" in payload and isinstance(payload["id"], str):
            dispute_id = dispute_id or payload["id"]
        if "evidence" in payload and isinstance(payload["evidence"], dict):
            evidence_dict = payload["evidence"]
        elif "payload" in payload and isinstance(payload["payload"], dict):
            # Webhook payload structure
            disp_entity = payload.get("payload", {}).get("dispute", {}).get("entity", {})
            if isinstance(disp_entity, dict):
                dispute_id = dispute_id or disp_entity.get("id")
                evidence_dict = disp_entity.get("evidence")
        else:
            # Assume payload is the evidence dict directly
            evidence_dict = payload
    else:
        result.warnings.append(
            f"Unsupported evidence payload type: {type(payload).__name__}"
        )
        return result

    if not evidence_dict or not isinstance(evidence_dict, dict):
        result.warnings.append("Evidence object is empty or missing")
        return result

    # Process all categories in evidence_dict
    for category_key, category_val in evidence_dict.items():
        if category_val is None:
            # Ignore null category per requirements
            continue

        if category_key not in SUPPORTED_EVIDENCE_CATEGORIES:
            result.warnings.append(
                f"Ignored unsupported evidence category: '{category_key}'"
            )
            continue

        if category_key == "others":
            _process_others_category(
                category_val, dispute_id, ref_map, result
            )
        else:
            _process_standard_category(
                category_key, category_val, dispute_id, ref_map, result
            )

    # Return insertion-ordered references
    result.references = list(ref_map.values())
    return result


def _process_standard_category(
    category_key: str,
    category_val: Any,
    dispute_id: str | None,
    ref_map: dict[str, EvidenceReference],
    result: EvidenceReferenceExtractionResult,
) -> None:
    """Process a standard evidence category (e.g. shipping_proof, billing_proof)."""
    items_to_process: list[Any] = []

    if isinstance(category_val, str):
        items_to_process = [category_val]
    elif isinstance(category_val, (list, tuple)):
        if not category_val:
            # Ignore empty arrays per requirements
            return
        items_to_process = list(category_val)
    else:
        result.invalid_items.append(
            EvidenceReferenceInvalidItem(
                category=category_key,
                raw_value=category_val,
                reason=f"Expected list or string for '{category_key}', got {type(category_val).__name__}",
            )
        )
        return

    for item in items_to_process:
        valid_doc_id, error_reason = validate_document_id(item)

        if valid_doc_id:
            _add_or_update_reference(
                doc_id=valid_doc_id,
                category=category_key,
                subtype=None,
                dispute_id=dispute_id,
                ref_map=ref_map,
            )
        else:
            result.invalid_items.append(
                EvidenceReferenceInvalidItem(
                    category=category_key,
                    raw_value=item,
                    reason=error_reason or "Invalid document ID",
                )
            )


def _process_others_category(
    others_val: Any,
    dispute_id: str | None,
    ref_map: dict[str, EvidenceReference],
    result: EvidenceReferenceExtractionResult,
) -> None:
    """
    Process the 'others' evidence category.

    Supports documented forms:
    1. String ID: "doc_123"
    2. Object form: {"type": "passport", "document_ids": ["doc_123"]}
    3. List of strings, objects, or mixed items
    """
    items: list[Any] = []

    if isinstance(others_val, dict):
        items = [others_val]
    elif isinstance(others_val, str):
        items = [others_val]
    elif isinstance(others_val, (list, tuple)):
        if not others_val:
            return
        items = list(others_val)
    else:
        result.invalid_items.append(
            EvidenceReferenceInvalidItem(
                category="others",
                raw_value=others_val,
                reason=f"Expected list or dict for 'others', got {type(others_val).__name__}",
            )
        )
        return

    for item in items:
        if isinstance(item, str):
            valid_doc_id, error_reason = validate_document_id(item)
            if valid_doc_id:
                _add_or_update_reference(
                    doc_id=valid_doc_id,
                    category="others",
                    subtype=None,
                    dispute_id=dispute_id,
                    ref_map=ref_map,
                )
            else:
                result.invalid_items.append(
                    EvidenceReferenceInvalidItem(
                        category="others",
                        raw_value=item,
                        reason=error_reason or "Invalid document ID in 'others'",
                    )
                )

        elif isinstance(item, dict):
            subtype = item.get("type")
            if subtype is not None and not isinstance(subtype, str):
                subtype = str(subtype)

            doc_ids_raw = (
                item.get("document_ids")
                or item.get("document_id")
                or item.get("id")
            )

            doc_id_list: list[Any] = []
            if isinstance(doc_ids_raw, str):
                doc_id_list = [doc_ids_raw]
            elif isinstance(doc_ids_raw, (list, tuple)):
                doc_id_list = list(doc_ids_raw)
            else:
                result.invalid_items.append(
                    EvidenceReferenceInvalidItem(
                        category="others",
                        raw_value=item,
                        reason="Malformed 'others' object: missing or invalid 'document_ids'",
                    )
                )
                continue

            if not doc_id_list:
                result.warnings.append("Empty 'document_ids' in 'others' object")
                continue

            for doc_id_item in doc_id_list:
                valid_doc_id, error_reason = validate_document_id(doc_id_item)
                if valid_doc_id:
                    _add_or_update_reference(
                        doc_id=valid_doc_id,
                        category="others",
                        subtype=subtype,
                        dispute_id=dispute_id,
                        ref_map=ref_map,
                    )
                else:
                    result.invalid_items.append(
                        EvidenceReferenceInvalidItem(
                            category="others",
                            raw_value=doc_id_item,
                            reason=error_reason or "Invalid document ID in 'others' object",
                        )
                    )

        else:
            result.invalid_items.append(
                EvidenceReferenceInvalidItem(
                    category="others",
                    raw_value=item,
                    reason=f"Unexpected item type in 'others': {type(item).__name__}",
                )
            )


def _add_or_update_reference(
    doc_id: str,
    category: str,
    subtype: str | None,
    dispute_id: str | None,
    ref_map: dict[str, EvidenceReference],
) -> None:
    """
    Add a new EvidenceReference or merge category into an existing reference.

    Ensures deduplication by doc_id while preserving all associated categories.
    """
    if doc_id in ref_map:
        existing = ref_map[doc_id]
        if category not in existing.categories:
            existing.categories.append(category)
        if subtype and not existing.evidence_subtype:
            existing.evidence_subtype = subtype
    else:
        ref_map[doc_id] = EvidenceReference(
            razorpay_doc_id=doc_id,
            razorpay_evidence_type=category,
            categories=[category],
            evidence_subtype=subtype,
            source_dispute_id=dispute_id,
        )
