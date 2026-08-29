"""
Unit Test Suite: Razorpay Evidence Reference Extractor — Task 3.3A

Tests safe extraction of document references from Razorpay evidence payloads:
- Single & multiple documents
- Null & empty evidence categories
- All supported Razorpay evidence categories
- 'others' object forms (single dict, list of dicts, mixed)
- Deduplication across same/different categories
- Malformed document IDs (path traversal, non-string, length > 64)
- Malformed 'others' payloads
- Missing & empty evidence objects
- Output determinism & schema compliance
"""

import pytest

from backend.app.schemas.evidence_reference import (
    EvidenceReference,
    EvidenceReferenceExtractionResult,
    EvidenceReferenceInvalidItem,
)
from backend.app.schemas.razorpay import RazorpayDisputeResponse
from backend.app.services.evidence_reference_extractor import (
    SUPPORTED_EVIDENCE_CATEGORIES,
    extract_evidence_references,
    validate_document_id,
)

DISPUTE_ID = "disp_AHfqOvkldwsbqt"


# ===========================================================================
# 1. DOCUMENT ID VALIDATION TESTS
# ===========================================================================


class TestDocumentIDValidation:
    """Test document ID validation & security filtering."""

    def test_valid_document_id(self):
        valid_id, err = validate_document_id("doc_AHfqOvkldwsbqt")
        assert valid_id == "doc_AHfqOvkldwsbqt"
        assert err is None

    def test_null_document_id(self):
        valid_id, err = validate_document_id(None)
        assert valid_id is None
        assert "None" in err

    def test_non_string_document_id(self):
        for val in [12345, True, False, 45.67, ["doc_1"], {"id": "doc_1"}]:
            valid_id, err = validate_document_id(val)
            assert valid_id is None
            assert "must be a string" in err

    def test_empty_and_whitespace_id(self):
        for val in ["", "   ", "\t\n"]:
            valid_id, err = validate_document_id(val)
            assert valid_id is None
            assert "empty" in err

    def test_excessively_long_id(self):
        long_id = "doc_" + "a" * 65
        valid_id, err = validate_document_id(long_id)
        assert valid_id is None
        assert "exceeds maximum length" in err

    def test_path_traversal_ids_rejected(self):
        invalid_ids = [
            "../doc_123",
            "doc_123/sub",
            "doc_123\\sub",
            "doc_123:etc",
            "doc_123\x00null",
            "doc_123%00null",
            "..",
        ]
        for val in invalid_ids:
            valid_id, err = validate_document_id(val)
            assert valid_id is None, f"Expected '{val}' to be rejected"
            assert "unsafe" in err or "invalid" in err


# ===========================================================================
# 2. EVIDENCE REFERENCE EXTRACTION TESTS
# ===========================================================================


class TestEvidenceReferenceExtractor:
    """Test extract_evidence_references function."""

    def test_single_shipping_document(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "shipping_proof": ["doc_shipping_001"],
            },
        }
        res = extract_evidence_references(payload)

        assert isinstance(res, EvidenceReferenceExtractionResult)
        assert len(res.references) == 1
        ref = res.references[0]
        assert ref.razorpay_doc_id == "doc_shipping_001"
        assert ref.razorpay_evidence_type == "shipping_proof"
        assert ref.categories == ["shipping_proof"]
        assert ref.source_dispute_id == DISPUTE_ID
        assert len(res.warnings) == 0
        assert len(res.invalid_items) == 0

    def test_multiple_documents(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "shipping_proof": ["doc_shipping_001", "doc_shipping_002"],
                "billing_proof": ["doc_billing_001"],
            },
        }
        res = extract_evidence_references(payload)

        assert len(res.references) == 3
        doc_ids = [r.razorpay_doc_id for r in res.references]
        assert doc_ids == ["doc_shipping_001", "doc_shipping_002", "doc_billing_001"]

    def test_null_evidence_category(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "shipping_proof": ["doc_shipping_001"],
                "cancellation_proof": None,
                "refund_confirmation": None,
            },
        }
        res = extract_evidence_references(payload)

        assert len(res.references) == 1
        assert res.references[0].razorpay_doc_id == "doc_shipping_001"
        assert len(res.invalid_items) == 0

    def test_empty_evidence_category(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "shipping_proof": [],
                "billing_proof": [],
            },
        }
        res = extract_evidence_references(payload)

        assert len(res.references) == 0
        assert len(res.invalid_items) == 0

    def test_all_supported_categories(self):
        all_categories = [
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
            "others",
        ]
        evidence_dict = {}
        for idx, cat in enumerate(all_categories):
            if cat == "others":
                evidence_dict[cat] = [{"type": "custom_doc", "document_ids": [f"doc_{idx}"]}]
            else:
                evidence_dict[cat] = [f"doc_{idx}"]

        payload = {"id": DISPUTE_ID, "evidence": evidence_dict}
        res = extract_evidence_references(payload)

        assert len(res.references) == len(all_categories)
        extracted_cats = {r.razorpay_evidence_type for r in res.references}
        assert extracted_cats == set(all_categories)

    def test_others_object(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "others": {
                    "type": "passport_scan",
                    "document_ids": ["doc_passport_001"],
                }
            },
        }
        res = extract_evidence_references(payload)

        assert len(res.references) == 1
        ref = res.references[0]
        assert ref.razorpay_doc_id == "doc_passport_001"
        assert ref.razorpay_evidence_type == "others"
        assert ref.evidence_subtype == "passport_scan"

    def test_multiple_others_objects(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "others": [
                    {"type": "passport_scan", "document_ids": ["doc_passport_001"]},
                    {"type": "utility_bill", "document_ids": ["doc_utility_001", "doc_utility_002"]},
                ]
            },
        }
        res = extract_evidence_references(payload)

        assert len(res.references) == 3
        subtypes = [r.evidence_subtype for r in res.references]
        assert subtypes == ["passport_scan", "utility_bill", "utility_bill"]

    def test_duplicate_document_id_in_same_category(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "shipping_proof": ["doc_001", "doc_001", "doc_001"],
            },
        }
        res = extract_evidence_references(payload)

        assert len(res.references) == 1
        ref = res.references[0]
        assert ref.razorpay_doc_id == "doc_001"
        assert ref.categories == ["shipping_proof"]

    def test_same_document_in_multiple_categories(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "shipping_proof": ["doc_multi_001"],
                "billing_proof": ["doc_multi_001"],
                "explanation_letter": ["doc_multi_001"],
            },
        }
        res = extract_evidence_references(payload)

        # Must return ONE document reference with all associated categories preserved
        assert len(res.references) == 1
        ref = res.references[0]
        assert ref.razorpay_doc_id == "doc_multi_001"
        assert ref.razorpay_evidence_type == "shipping_proof"
        assert ref.categories == ["shipping_proof", "billing_proof", "explanation_letter"]

    def test_malformed_document_id(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "shipping_proof": ["doc_valid_001", "../path_traversal", "   ", "doc_valid_002"],
            },
        }
        res = extract_evidence_references(payload)

        assert len(res.references) == 2
        ref_ids = [r.razorpay_doc_id for r in res.references]
        assert ref_ids == ["doc_valid_001", "doc_valid_002"]

        assert len(res.invalid_items) == 2
        invalid_reasons = [inv.reason for inv in res.invalid_items]
        assert any("unsafe" in r or "path" in r for r in invalid_reasons)
        assert any("empty" in r for r in invalid_reasons)

    def test_non_string_document_id(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "shipping_proof": [12345, True, {"id": "nested_dict"}, "doc_valid_001"],
            },
        }
        res = extract_evidence_references(payload)

        assert len(res.references) == 1
        assert res.references[0].razorpay_doc_id == "doc_valid_001"
        assert len(res.invalid_items) == 3

    def test_malformed_others(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "others": [
                    {"type": "bad_object"},  # Missing document_ids
                    12345,  # Non-dict/string element
                    "doc_valid_others",
                ]
            },
        }
        res = extract_evidence_references(payload)

        assert len(res.references) == 1
        assert res.references[0].razorpay_doc_id == "doc_valid_others"
        assert len(res.invalid_items) == 2

    def test_missing_evidence(self):
        res1 = extract_evidence_references(None)
        assert len(res1.references) == 0
        assert len(res1.warnings) > 0

        res2 = extract_evidence_references({})
        assert len(res2.references) == 0
        assert len(res2.warnings) > 0

        res3 = extract_evidence_references({"id": DISPUTE_ID})
        assert len(res3.references) == 0
        assert len(res3.warnings) > 0

    def test_empty_evidence_object(self):
        payload = {"id": DISPUTE_ID, "evidence": {}}
        res = extract_evidence_references(payload)

        assert len(res.references) == 0
        assert len(res.warnings) == 1
        assert "empty or missing" in res.warnings[0]
        assert len(res.invalid_items) == 0


    def test_deterministic_output(self):
        payload = {
            "id": DISPUTE_ID,
            "evidence": {
                "shipping_proof": ["doc_001", "doc_002"],
                "billing_proof": ["doc_003", "doc_001"],
                "others": [{"type": "policy", "document_ids": ["doc_004"]}],
            },
        }

        # Run extraction 5 times
        results = [extract_evidence_references(payload) for _ in range(5)]

        for r in results[1:]:
            assert r.model_dump() == results[0].model_dump()

    def test_dispute_response_schema_input(self):
        # Verify compatibility when passing RazorpayDisputeResponse
        raw_dispute = {
            "id": "disp_AHfqOvkldwsbqt",
            "entity": "dispute",
            "payment_id": "pay_test_001",
            "amount": 150000,
            "currency": "INR",
            "amount_deducted": 150000,
            "reason_code": "chargeback",
            "status": "open",
            "created_at": 1735603200,
        }
        dispute_obj = RazorpayDisputeResponse.model_validate(raw_dispute)

        # Pass dispute_obj with raw payload dict containing evidence
        payload_with_evidence = {
            **raw_dispute,
            "evidence": {"shipping_proof": ["doc_resp_schema_001"]},
        }
        res = extract_evidence_references(payload_with_evidence, source_dispute_id=dispute_obj.id)

        assert len(res.references) == 1
        assert res.references[0].razorpay_doc_id == "doc_resp_schema_001"
        assert res.references[0].source_dispute_id == "disp_AHfqOvkldwsbqt"
