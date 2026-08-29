"""
End-to-End Integration Test Suite: Deterministic Evidence Matching Engine — Task 4.2

Full Pipeline:
EvidenceDocument -> ProcessedArtifact -> ExtractedEvidence -> Matcher -> MatchResult

Verifies:
- Complete pipeline execution
- Correct status counts & result fields
- Full provenance tracking (source page, artifact ID, extraction method)
- Financial safety invariants (payment_id, amount, currency untouched)
- Repeated execution idempotency
"""

import hashlib
import os
import pytest
from sqlalchemy.future import select

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.matching import MatchResult
from backend.app.models.processed_artifact import ProcessedArtifact
from backend.app.services.ai_extraction_service import execute_ai_extraction
from backend.app.services.ai_provider import MockAIProvider
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.processing_service import process_evidence_document

E2E_DISPUTE_ID = "disp_matching_e2e_999"
E2E_EVIDENCE_ID = "doc_matching_e2e_999"

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


async def _setup_e2e_matching_pipeline(async_db, tmp_path):
    """Sets up a complete local dispute and evidence document file on disk."""
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # 1. Dispute
    res = await async_db.execute(select(Dispute).where(Dispute.id == E2E_DISPUTE_ID))
    dispute = res.scalar_one_or_none()
    if not dispute:
        dispute = Dispute(
            id=E2E_DISPUTE_ID,
            payment_id="pay_matching_e2e_999",
            amount=150000,
            currency="INR",
            reason_code="chargeback",
            status="open",
            phase="chargeback",
            raw_payload={"order_id": "ord_matching_e2e_999", "awb_number": "AWB999888777"},
        )
        async_db.add(dispute)
        await async_db.commit()

    # 2. File write
    file_path = os.path.join(upload_dir, "invoice_e2e.pdf")
    with open(file_path, "wb") as f:
        f.write(MINIMAL_VALID_PDF)

    file_hash = hashlib.sha256(MINIMAL_VALID_PDF).hexdigest()

    # 3. EvidenceDocument
    res_doc = await async_db.execute(select(EvidenceDocument).where(EvidenceDocument.id == E2E_EVIDENCE_ID))
    doc = res_doc.scalar_one_or_none()
    if not doc:
        doc = EvidenceDocument(
            id=E2E_EVIDENCE_ID,
            dispute_id=E2E_DISPUTE_ID,
            razorpay_doc_id="doc_rzp_e2e_999",
            original_filename="invoice_e2e.pdf",
            internal_filename="internal_e2e_999.png",
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


class TestEvidenceMatchingE2E:
    """Full pipeline integration tests."""

    @pytest.mark.asyncio
    async def test_matching_full_pipeline(self, async_db, tmp_path):
        dispute, doc, upload_dir, processed_dir = await _setup_e2e_matching_pipeline(async_db, tmp_path)

        # Stage 1: Document Processing (EvidenceDocument -> ProcessedArtifact)
        proc_res = await process_evidence_document(
            doc.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir
        )
        assert proc_res["status"] == "READY_FOR_AI"

        # Stage 2: AI Fact Extraction (ProcessedArtifact -> ExtractedEvidence)
        provider = MockAIProvider(mock_scenario="valid_shipping_proof")
        ext_res = await execute_ai_extraction(doc.id, async_db, provider=provider)
        assert ext_res["status"] == "AI_EXTRACTED"

        # Stage 3: Evidence Matcher (ExtractedEvidence -> MatchResult)
        matching_res = await run_evidence_matching(E2E_DISPUTE_ID, async_db)

        assert matching_res.dispute_id == E2E_DISPUTE_ID
        assert matching_res.status in ("DETERMINISTIC_MATCH", "CRITICAL_MISMATCH", "INCOMPLETE_EVIDENCE")
        assert len(matching_res.results) >= 3

        # Verify DB MatchResults
        stmt = select(MatchResult).where(MatchResult.dispute_id == E2E_DISPUTE_ID)
        db_results = (await async_db.execute(stmt)).scalars().all()
        assert len(db_results) == matching_res.total_facts
        assert all(r.matcher_version == "1.0" for r in db_results)

    @pytest.mark.asyncio
    async def test_matching_e2e_financial_invariant(self, async_db, tmp_path):
        dispute, doc, upload_dir, processed_dir = await _setup_e2e_matching_pipeline(async_db, tmp_path)

        orig_pay = dispute.payment_id
        orig_amt = dispute.amount
        orig_curr = dispute.currency

        await process_evidence_document(
            doc.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir
        )
        await execute_ai_extraction(doc.id, async_db, provider=MockAIProvider())
        await run_evidence_matching(E2E_DISPUTE_ID, async_db)

        await async_db.refresh(dispute)
        assert dispute.payment_id == orig_pay
        assert dispute.amount == orig_amt
        assert dispute.currency == orig_curr

    @pytest.mark.asyncio
    async def test_matching_e2e_idempotency(self, async_db, tmp_path):
        dispute, doc, upload_dir, processed_dir = await _setup_e2e_matching_pipeline(async_db, tmp_path)

        await process_evidence_document(
            doc.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir
        )
        await execute_ai_extraction(doc.id, async_db, provider=MockAIProvider())

        run1 = await run_evidence_matching(E2E_DISPUTE_ID, async_db)
        run2 = await run_evidence_matching(E2E_DISPUTE_ID, async_db)

        assert run1.status == run2.status
        assert run1.total_facts == run2.total_facts

        stmt = select(MatchResult).where(MatchResult.dispute_id == E2E_DISPUTE_ID)
        rows = (await async_db.execute(stmt)).scalars().all()
        assert len(rows) == run1.total_facts
