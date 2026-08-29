"""
Unit Test Suite: Deterministic Evidence Matching Engine — Task 4.2

Tests:
- Deterministic comparison functions (compare_exact, compare_amount, compare_currency, compare_date, compare_email, compare_phone, compare_tracking_id)
- Amount minor integer comparison (paise) vs floating point or formatted strings
- Currency uppercase comparison
- Missing facts vs Ambiguous facts
- Financial safety invariants (dispute payment_id, amount, currency untouched)
- Zero policy decision methods verification
- Idempotency & provenance tracking
- API router endpoint contract
"""

import inspect
import pytest
from sqlalchemy.future import select

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.matching import MatchResult
from backend.app.models.processed_artifact import ProcessedArtifact
from backend.app.schemas.matching import MatchStatus
from backend.app.services.matching_service import (
    compare_amount,
    compare_currency,
    compare_date,
    compare_email,
    compare_exact,
    compare_phone,
    compare_tracking_id,
    run_evidence_matching,
)

TEST_DISPUTE_ID = "disp_match_unit_100"
TEST_EVIDENCE_ID = "doc_match_unit_100"
TEST_ARTIFACT_ID = "art_match_unit_100"


async def _setup_matching_fixtures(async_db, amount=149900, currency="INR", ext_amount=149900, ext_pay="pay_match_100"):
    """Helper fixture setup for dispute, evidence document, artifact, and extraction."""
    # Setup Dispute
    res = await async_db.execute(select(Dispute).where(Dispute.id == TEST_DISPUTE_ID))
    dispute = res.scalar_one_or_none()
    if not dispute:
        dispute = Dispute(
            id=TEST_DISPUTE_ID,
            payment_id="pay_match_100",
            amount=amount,
            currency=currency,
            reason_code="chargeback",
            status="open",
            phase="chargeback",
            raw_payload={"order_id": "ord_match_100", "awb_number": "AWB123456789"},
        )
        async_db.add(dispute)
        await async_db.commit()
    else:
        dispute.amount = amount
        dispute.currency = currency
        await async_db.commit()

    # Setup EvidenceDocument
    res_doc = await async_db.execute(select(EvidenceDocument).where(EvidenceDocument.id == TEST_EVIDENCE_ID))
    doc = res_doc.scalar_one_or_none()
    if not doc:
        doc = EvidenceDocument(
            id=TEST_EVIDENCE_ID,
            dispute_id=TEST_DISPUTE_ID,
            razorpay_doc_id="razor_doc_100",
            original_filename="invoice.pdf",
            internal_filename="internal_100.png",
            file_path="storage/uploads/test.pdf",
            file_hash="hash_100",
            file_size_bytes=1000,
            mime_type="application/pdf",
            document_type="invoice",
            processing_status="AI_EXTRACTED",
        )
        async_db.add(doc)
        await async_db.commit()

    # Setup ProcessedArtifact
    res_art = await async_db.execute(select(ProcessedArtifact).where(ProcessedArtifact.id == TEST_ARTIFACT_ID))
    art = res_art.scalar_one_or_none()
    if not art:
        art = ProcessedArtifact(
            id=TEST_ARTIFACT_ID,
            evidence_id=TEST_EVIDENCE_ID,
            page_number=1,
            file_path="storage/processed/page_001.png",
            width=800,
            height=1000,
            file_size_bytes=500,
            format="PNG",
            source_document_type="pdf",
        )
        async_db.add(art)
        await async_db.commit()

    # Setup ExtractedEvidence
    res_ext = await async_db.execute(select(ExtractedEvidence).where(ExtractedEvidence.document_id == TEST_EVIDENCE_ID))
    ext = res_ext.scalar_one_or_none()
    if ext:
        await async_db.delete(ext)
        await async_db.commit()

    ext = ExtractedEvidence(
        document_id=TEST_EVIDENCE_ID,
        document_type="invoice",
        payment_id=ext_pay,
        order_id="ord_match_100",
        amount_minor=ext_amount,
        currency="INR",
        awb_number="AWB123456789",
        delivery_date="2026-08-15",
        confidence_score=0.95,
        confidence_by_field={"payment_id": 0.95, "amount_minor": 0.95, "currency": 0.95},
        extracted_data={"document_type": "invoice"},
        raw_response={},
        model_name="mock-vision-v1",
        prompt_version="1.0",
        schema_version="1.0",
    )
    async_db.add(ext)
    await async_db.commit()

    return dispute, doc, ext


# ===========================================================================
# 1. DETERMINISTIC COMPARISON UTILITIES
# ===========================================================================


class TestComparisonUtilities:
    """Test individual comparison helper functions."""

    def test_compare_exact(self):
        st, norm, _ = compare_exact("pay_123", "pay_123")
        assert st == MatchStatus.MATCH
        assert norm == "pay_123"

        st_mis, _, _ = compare_exact("pay_123", "pay_999")
        assert st_mis == MatchStatus.MISMATCH

        st_null, _, _ = compare_exact("pay_123", None)
        assert st_null == MatchStatus.MISSING

    def test_compare_amount(self):
        # Integer minor units comparison
        st, obs, _ = compare_amount(149900, "₹1,499.00")
        assert st == MatchStatus.MATCH
        assert obs == "149900"

        st_mis, _, _ = compare_amount(149900, 99900)
        assert st_mis == MatchStatus.MISMATCH

        st_null, _, _ = compare_amount(149900, None)
        assert st_null == MatchStatus.MISSING

        st_amb, _, _ = compare_amount(149900, "invalid_amount_str")
        assert st_amb == MatchStatus.AMBIGUOUS

    def test_compare_currency(self):
        st, norm, _ = compare_currency("INR", "inr")
        assert st == MatchStatus.MATCH
        assert norm == "INR"

        st_mis, _, _ = compare_currency("INR", "USD")
        assert st_mis == MatchStatus.MISMATCH

        st_null, _, _ = compare_currency("INR", None)
        assert st_null == MatchStatus.MISSING

    def test_compare_date(self):
        st, norm, _ = compare_date("2026-08-15", "15 Aug 2026")
        assert st == MatchStatus.MATCH
        assert norm == "2026-08-15"

        st_mis, _, _ = compare_date("2026-08-15", "2026-08-20")
        assert st_mis == MatchStatus.MISMATCH

        st_amb, _, _ = compare_date("2026-08-15", "invalid_date")
        assert st_amb == MatchStatus.AMBIGUOUS

    def test_compare_email(self):
        st, norm, _ = compare_email("Customer@Example.COM", " customer@example.com ")
        assert st == MatchStatus.MATCH
        assert norm == "customer@example.com"

    def test_compare_phone(self):
        st, norm, _ = compare_phone("+91 (987) 654-3210", "+919876543210")
        assert st == MatchStatus.MATCH
        assert norm == "+919876543210"

    def test_compare_tracking_id(self):
        st, norm, _ = compare_tracking_id(" awb_12345 ", "AWB_12345")
        assert st == MatchStatus.MATCH
        assert norm == "AWB_12345"


# ===========================================================================
# 2. MATCHING ENGINE CORE TESTS
# ===========================================================================


class TestMatchingEngineCore:
    """Test run_evidence_matching execution, provenance, idempotency, and financial safety."""

    @pytest.mark.asyncio
    async def test_matching_happy_path(self, async_db):
        await _setup_matching_fixtures(async_db)

        result = await run_evidence_matching(TEST_DISPUTE_ID, async_db)

        assert result.dispute_id == TEST_DISPUTE_ID
        assert result.status == "DETERMINISTIC_MATCH"
        assert result.match_count >= 3
        assert result.mismatches_count == 0
        assert len(result.results) >= 3

        # Verify DB persistence
        stmt = select(MatchResult).where(MatchResult.dispute_id == TEST_DISPUTE_ID)
        rows = (await async_db.execute(stmt)).scalars().all()
        assert len(rows) >= 3
        assert any(r.fact_name == "amount_minor" and r.status == "MATCH" for r in rows)

    @pytest.mark.asyncio
    async def test_matching_amount_mismatch(self, async_db):
        await _setup_matching_fixtures(async_db, amount=149900, ext_amount=99900)

        result = await run_evidence_matching(TEST_DISPUTE_ID, async_db)

        assert result.status == "CRITICAL_MISMATCH"
        assert result.mismatches_count >= 1

        amt_res = next(r for r in result.results if r.fact_name == "amount_minor")
        assert amt_res.status == MatchStatus.MISMATCH
        assert amt_res.expected_value == "149900"
        assert amt_res.observed_value == "99900"

    @pytest.mark.asyncio
    async def test_financial_safety_invariant(self, async_db):
        dispute, _, _ = await _setup_matching_fixtures(async_db, amount=149900, currency="INR")

        orig_payment = dispute.payment_id
        orig_amount = dispute.amount
        orig_currency = dispute.currency

        await run_evidence_matching(TEST_DISPUTE_ID, async_db)

        await async_db.refresh(dispute)
        assert dispute.payment_id == orig_payment
        assert dispute.amount == orig_amount
        assert dispute.currency == orig_currency

    @pytest.mark.asyncio
    async def test_idempotent_matching(self, async_db):
        await _setup_matching_fixtures(async_db)

        run1 = await run_evidence_matching(TEST_DISPUTE_ID, async_db)
        run2 = await run_evidence_matching(TEST_DISPUTE_ID, async_db)

        assert run1.status == run2.status
        assert run1.total_facts == run2.total_facts
        assert run1.match_count == run2.match_count

        stmt = select(MatchResult).where(MatchResult.dispute_id == TEST_DISPUTE_ID)
        rows = (await async_db.execute(stmt)).scalars().all()
        assert len(rows) == run1.total_facts

    def test_no_policy_decision_methods(self):
        import backend.app.services.matching_service as svc
        assert not hasattr(svc, "decide_eligibility")
        assert not hasattr(svc, "evaluate_policy")
        assert not hasattr(svc, "create_contest")
        assert not hasattr(svc, "submit_contest")

    def test_api_endpoint_contract(self):
        from backend.app.api.matching import match_dispute_evidence_endpoint
        sig = inspect.signature(match_dispute_evidence_endpoint)
        params = list(sig.parameters.keys())
        assert "dispute_id" in params
        assert "amount" not in params
        assert "policy" not in params
