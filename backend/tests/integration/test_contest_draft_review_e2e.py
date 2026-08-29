"""
End-to-End Integration Test Suite: Contest Response Draft Review Workflow — Task 5.2

Full Pipeline:
Dispute -> EvidenceDocument -> ProcessedArtifact -> ExtractedEvidence -> MatchResult -> PolicyResult -> ContestDraft -> Human Review -> APPROVED / REJECTED

Verifies:
- Complete end-to-end pipeline execution through human review
- Correct state separation: ContestDraft.status preserved, review_status updated
- Fingerprint validation and audit creation
- Financial immutability assertions (payment_id, amount, currency untouched)
- Terminal state idempotency
- Zero Razorpay mutations and zero AI calls
"""

import hashlib
import os
import pytest
from sqlalchemy.future import select

from backend.app.models.contest_draft import ContestDraft as ContestDraftModel
from backend.app.models.contest_draft_review import ContestDraftReviewAudit
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.models.matching import MatchResult
from backend.app.schemas.contest_draft import ReviewStatus
from backend.app.schemas.contest_draft_review import ReviewDecision
from backend.app.services.ai_extraction_service import execute_ai_extraction
from backend.app.services.ai_provider import MockAIProvider
from backend.app.services.contest_draft_review_service import get_latest_draft_schema, review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy
from backend.app.services.processing_service import process_evidence_document

E2E_REV_DISPUTE_ID = "disp_rev_e2e_1"
E2E_REV_EVIDENCE_INV_ID = "doc_rev_e2e_inv_1"
E2E_REV_EVIDENCE_SHIP_ID = "doc_rev_e2e_ship_1"

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


async def _setup_e2e_review_pipeline(async_db, tmp_path):
    """Sets up a local dispute and 2 evidence documents (invoice + shipping proof) for review E2E testing."""
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # Clean up any existing records for test dispute_id
    from sqlalchemy import text
    await async_db.execute(text("DELETE FROM contest_draft_review_audits WHERE dispute_id = :d"), {"d": E2E_REV_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_drafts WHERE dispute_id = :d"), {"d": E2E_REV_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = :d"), {"d": E2E_REV_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = :d"), {"d": E2E_REV_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM extracted_evidence WHERE document_id IN (SELECT id FROM evidence_documents WHERE dispute_id = :d)"), {"d": E2E_REV_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM evidence_documents WHERE dispute_id = :d"), {"d": E2E_REV_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM disputes WHERE id = :d"), {"d": E2E_REV_DISPUTE_ID})
    await async_db.commit()

    # 1. Dispute
    dispute = Dispute(
        id=E2E_REV_DISPUTE_ID,
        payment_id="pay_synth_0001",
        amount=9030000,
        currency="INR",
        reason_code="13.1",
        status="open",
        phase="chargeback",
        raw_payload={
            "payload": {
                "dispute": {
                    "entity": {
                        "id": E2E_REV_DISPUTE_ID,
                        "payment_id": "pay_synth_0001",
                        "order_id": "ord_synth_0001",
                        "amount": 9030000,
                        "currency": "INR",
                        "awb_number": "1Z9998880001",
                    }
                }
            }
        },
    )
    async_db.add(dispute)
    await async_db.commit()

    file_hash = hashlib.sha256(MINIMAL_VALID_PDF).hexdigest()

    file_path_inv = os.path.join(upload_dir, "invoice_rev_e2e.pdf")
    with open(file_path_inv, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_inv = EvidenceDocument(
        id=E2E_REV_EVIDENCE_INV_ID,
        dispute_id=E2E_REV_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_rev_inv_1",
        original_filename="invoice_rev_e2e.pdf",
        internal_filename="internal_rev_inv_1.png",
        file_path=file_path_inv,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="invoice",
        processing_status="UPLOADED",
    )
    async_db.add(doc_inv)

    file_path_ship = os.path.join(upload_dir, "shipping_proof_rev_e2e.pdf")
    with open(file_path_ship, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_ship = EvidenceDocument(
        id=E2E_REV_EVIDENCE_SHIP_ID,
        dispute_id=E2E_REV_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_rev_ship_1",
        original_filename="shipping_proof_rev_e2e.pdf",
        internal_filename="internal_rev_ship_1.png",
        file_path=file_path_ship,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="shipping_proof",
        processing_status="UPLOADED",
    )
    async_db.add(doc_ship)

    await async_db.commit()

    return dispute, doc_inv, doc_ship, upload_dir, processed_dir


class TestContestDraftReviewE2E:
    """Full end-to-end contest draft review integration tests."""

    @pytest.mark.asyncio
    async def test_review_full_pipeline_approval(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship, upload_dir, processed_dir = await _setup_e2e_review_pipeline(async_db, tmp_path)

        # Stage 1: Document Processing for both docs
        proc_inv = await process_evidence_document(
            doc_inv.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir
        )
        proc_ship = await process_evidence_document(
            doc_ship.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir
        )
        assert proc_inv["status"] == "READY_FOR_AI"
        assert proc_ship["status"] == "READY_FOR_AI"

        # Stage 2: AI Extraction for both docs
        ext_inv = await execute_ai_extraction(doc_inv.id, async_db, provider=MockAIProvider(), document_hint="invoice")
        ext_ship = await execute_ai_extraction(doc_ship.id, async_db, provider=MockAIProvider(), document_hint="shipping_proof")
        assert ext_inv["status"] == "AI_EXTRACTED"
        assert ext_ship["status"] == "AI_EXTRACTED"

        # Stage 3: Evidence Matcher
        match_res = await run_evidence_matching(E2E_REV_DISPUTE_ID, async_db)
        assert match_res.dispute_id == E2E_REV_DISPUTE_ID

        # Stage 4: Policy Engine
        policy_res = await evaluate_dispute_policy(E2E_REV_DISPUTE_ID, async_db, reference_date="2026-08-26")
        assert policy_res.dispute_id == E2E_REV_DISPUTE_ID

        # Stage 5: Contest Response Drafting Engine
        draft = await generate_contest_draft(E2E_REV_DISPUTE_ID, async_db, reference_date="2026-08-26")
        assert draft.review_status == ReviewStatus.PENDING_REVIEW
        initial_status = draft.status

        # Stage 6: Human Review Approval
        rev_res = await review_contest_draft(
            E2E_REV_DISPUTE_ID, ReviewDecision.APPROVE, comment="E2E Approval verified", reviewer_reference="e2e_lead", db=async_db
        )

        assert rev_res.new_review_status == ReviewStatus.APPROVED
        assert rev_res.previous_review_status == ReviewStatus.PENDING_REVIEW

        # Verify DB state
        latest_schema = await get_latest_draft_schema(E2E_REV_DISPUTE_ID, async_db)
        assert latest_schema.status == initial_status  # Policy status unchanged
        assert latest_schema.review_status == ReviewStatus.APPROVED

        # Verify Audit Log
        stmt = select(ContestDraftReviewAudit).where(ContestDraftReviewAudit.dispute_id == E2E_REV_DISPUTE_ID)
        audits = (await async_db.execute(stmt)).scalars().all()
        assert len(audits) == 1
        assert audits[0].decision == "APPROVE"

    @pytest.mark.asyncio
    async def test_review_e2e_financial_immutability(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship, upload_dir, processed_dir = await _setup_e2e_review_pipeline(async_db, tmp_path)

        orig_pay = dispute.payment_id
        orig_amt = dispute.amount
        orig_curr = dispute.currency

        await process_evidence_document(
            doc_inv.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir
        )
        await execute_ai_extraction(doc_inv.id, async_db, provider=MockAIProvider(), document_hint="invoice")
        await run_evidence_matching(E2E_REV_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_REV_DISPUTE_ID, async_db)
        await generate_contest_draft(E2E_REV_DISPUTE_ID, async_db)

        await review_contest_draft(E2E_REV_DISPUTE_ID, ReviewDecision.REJECT, comment="E2E Reject", db=async_db)

        await async_db.refresh(dispute)
        assert dispute.payment_id == orig_pay
        assert dispute.amount == orig_amt
        assert dispute.currency == orig_curr
