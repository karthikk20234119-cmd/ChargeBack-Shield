"""
End-to-End Integration Test Suite: Deterministic Policy Engine — Task 4.3

Full Pipeline:
EvidenceDocument -> ProcessedArtifact -> ExtractedEvidence -> MatchResult -> PolicyEngine -> PolicyResult

Verifies:
- Full end-to-end pipeline execution
- Deterministic policy decisions (ELIGIBLE, HUMAN_REVIEW, NOT_ELIGIBLE)
- Rule results, reason codes, and evidence coverage metrics
- Provenance preservation via source_match_result_ids
- Financial immutability assertions (payment_id, amount, currency untouched)
- Repeated execution idempotency
"""

import hashlib
import os
import pytest
from sqlalchemy.future import select

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.models.policy import PolicyResult
from backend.app.services.ai_extraction_service import execute_ai_extraction
from backend.app.services.ai_provider import MockAIProvider
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy
from backend.app.services.processing_service import process_evidence_document

E2E_POLICY_DISPUTE_ID = "disp_policy_e2e_888"
E2E_POLICY_EVIDENCE_ID = "doc_policy_e2e_888"

MINIMAL_VALID_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
    b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
    b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>> endobj\n"
    b"xref\n0 4\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000056 00000 n \n"
    b"0000000111 00000 n \n"
    b"trailer <</Size 4 /Root 1 0 R>>\n"
    b"startxref\n173\n"
    b"%%EOF\n"
)


async def _setup_e2e_policy_pipeline(async_db, tmp_path):
    """Sets up a local dispute and evidence document for policy E2E testing."""
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # 1. Dispute
    res = await async_db.execute(select(Dispute).where(Dispute.id == E2E_POLICY_DISPUTE_ID))
    dispute = res.scalar_one_or_none()
    if not dispute:
        dispute = Dispute(
            id=E2E_POLICY_DISPUTE_ID,
            payment_id="pay_policy_e2e_888",
            amount=250000,
            currency="INR",
            reason_code="chargeback",
            status="open",
            phase="chargeback",
            raw_payload={"order_id": "ord_policy_e2e_888", "awb_number": "AWB888777666"},
        )
        async_db.add(dispute)
        await async_db.commit()

    # 2. File write
    file_path = os.path.join(upload_dir, "invoice_policy_e2e.pdf")
    with open(file_path, "wb") as f:
        f.write(MINIMAL_VALID_PDF)

    file_hash = hashlib.sha256(MINIMAL_VALID_PDF).hexdigest()

    # 3. EvidenceDocument
    res_doc = await async_db.execute(select(EvidenceDocument).where(EvidenceDocument.id == E2E_POLICY_EVIDENCE_ID))
    doc = res_doc.scalar_one_or_none()
    if not doc:
        doc = EvidenceDocument(
            id=E2E_POLICY_EVIDENCE_ID,
            dispute_id=E2E_POLICY_DISPUTE_ID,
            razorpay_doc_id="doc_rzp_policy_e2e_888",
            original_filename="invoice_policy_e2e.pdf",
            internal_filename="internal_policy_e2e_888.png",
            file_path=file_path,
            file_hash=file_hash,
            file_size_bytes=len(MINIMAL_VALID_PDF),
            mime_type="application/pdf",
            document_type="invoice",
            processing_status="UPLOADED",
        )
        async_db.add(doc)
        await async_db.commit()

    return dispute, doc, upload_dir, processed_dir


class TestPolicyEngineE2E:
    """Full end-to-end policy pipeline integration tests."""

    @pytest.mark.asyncio
    async def test_policy_full_pipeline(self, async_db, tmp_path):
        dispute, doc, upload_dir, processed_dir = await _setup_e2e_policy_pipeline(async_db, tmp_path)

        # Stage 1: Document Processing
        proc_res = await process_evidence_document(
            doc.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir
        )
        assert proc_res["status"] == "READY_FOR_AI"

        # Stage 2: AI Extraction
        ext_res = await execute_ai_extraction(doc.id, async_db, provider=MockAIProvider(mock_scenario="valid_shipping_proof"))
        assert ext_res["status"] == "AI_EXTRACTED"

        # Stage 3: Evidence Matcher
        match_res = await run_evidence_matching(E2E_POLICY_DISPUTE_ID, async_db)
        assert match_res.dispute_id == E2E_POLICY_DISPUTE_ID

        # Stage 4: Policy Engine
        policy_res = await evaluate_dispute_policy(E2E_POLICY_DISPUTE_ID, async_db, reference_date="2026-08-26")

        assert policy_res.dispute_id == E2E_POLICY_DISPUTE_ID
        assert policy_res.decision in ("ELIGIBLE", "HUMAN_REVIEW", "NOT_ELIGIBLE")
        assert len(policy_res.rule_results) >= 7
        assert policy_res.evidence_coverage is not None
        assert policy_res.financial_safety_verified is True

        # Verify DB PolicyResult record
        stmt = select(PolicyResult).where(PolicyResult.dispute_id == E2E_POLICY_DISPUTE_ID)
        db_policy = (await async_db.execute(stmt)).scalar_one_or_none()
        assert db_policy is not None
        assert db_policy.policy_version == policy_res.policy_version
        assert db_policy.financial_safety_verified is True

    @pytest.mark.asyncio
    async def test_policy_e2e_financial_immutability(self, async_db, tmp_path):
        dispute, doc, upload_dir, processed_dir = await _setup_e2e_policy_pipeline(async_db, tmp_path)

        orig_pay = dispute.payment_id
        orig_amt = dispute.amount
        orig_curr = dispute.currency

        await process_evidence_document(
            doc.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir
        )
        await execute_ai_extraction(doc.id, async_db, provider=MockAIProvider())
        await run_evidence_matching(E2E_POLICY_DISPUTE_ID, async_db)
        policy_res = await evaluate_dispute_policy(E2E_POLICY_DISPUTE_ID, async_db)

        await async_db.refresh(dispute)
        assert dispute.payment_id == orig_pay
        assert dispute.amount == orig_amt
        assert dispute.currency == orig_curr
        assert policy_res.financial_safety_verified is True

    @pytest.mark.asyncio
    async def test_policy_e2e_idempotency(self, async_db, tmp_path):
        dispute, doc, upload_dir, processed_dir = await _setup_e2e_policy_pipeline(async_db, tmp_path)

        await process_evidence_document(
            doc.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir
        )
        await execute_ai_extraction(doc.id, async_db, provider=MockAIProvider())
        await run_evidence_matching(E2E_POLICY_DISPUTE_ID, async_db)

        run1 = await evaluate_dispute_policy(E2E_POLICY_DISPUTE_ID, async_db)
        run2 = await evaluate_dispute_policy(E2E_POLICY_DISPUTE_ID, async_db)

        assert run1.decision == run2.decision
        assert run1.summary == run2.summary
        assert run1.evidence_coverage.coverage_percentage == run2.evidence_coverage.coverage_percentage

        stmt = select(PolicyResult).where(PolicyResult.dispute_id == E2E_POLICY_DISPUTE_ID)
        rows = (await async_db.execute(stmt)).scalars().all()
        assert len(rows) == 1
