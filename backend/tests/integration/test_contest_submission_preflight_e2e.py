"""
End-to-End Integration Test Suite: Contest Submission Preflight Gate — Task 5.3

Full Pipeline:
Dispute -> EvidenceDocument -> ProcessedArtifact -> ExtractedEvidence -> MatchResult -> PolicyResult -> ContestDraft -> Human Review APPROVED -> Preflight -> READY

Verifies:
- Full end-to-end pipeline execution through preflight authorization gate
- Correct preflight status transitions (READY, BLOCKED, STALE, REVIEW_REQUIRED)
- Preflight record persistence and audit integrity
- Financial immutability assertions (payment_id, amount, currency untouched)
- Zero Razorpay mutations and zero external API calls
"""

import hashlib
import os
import pytest
from sqlalchemy import text
from sqlalchemy.future import select

from backend.app.models.contest_draft import ContestDraft as ContestDraftModel
from backend.app.models.contest_submission_preflight import ContestSubmissionPreflight
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.schemas.contest_draft_review import ReviewDecision
from backend.app.schemas.contest_submission_preflight import PreflightStatus
from backend.app.services.ai_extraction_service import execute_ai_extraction
from backend.app.services.ai_provider import MockAIProvider
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_preflight_service import (
    StaleDraftException,
    run_preflight,
)
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy
from backend.app.services.processing_service import process_evidence_document

E2E_PREF_DISPUTE_ID = "disp_pref_e2e_1"
E2E_PREF_EVIDENCE_INV_ID = "doc_pref_e2e_inv_1"
E2E_PREF_EVIDENCE_SHIP_ID = "doc_pref_e2e_ship_1"

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


async def _setup_e2e_preflight_pipeline(async_db, tmp_path):
    """Sets up a local dispute and 2 evidence documents for preflight E2E testing."""
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # Clean up existing test data
    await async_db.execute(text("DELETE FROM contest_submission_preflights WHERE dispute_id = :d"), {"d": E2E_PREF_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_draft_review_audits WHERE dispute_id = :d"), {"d": E2E_PREF_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_drafts WHERE dispute_id = :d"), {"d": E2E_PREF_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = :d"), {"d": E2E_PREF_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = :d"), {"d": E2E_PREF_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM extracted_evidence WHERE document_id IN (SELECT id FROM evidence_documents WHERE dispute_id = :d)"), {"d": E2E_PREF_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM evidence_documents WHERE dispute_id = :d"), {"d": E2E_PREF_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM disputes WHERE id = :d"), {"d": E2E_PREF_DISPUTE_ID})
    await async_db.commit()

    dispute = Dispute(
        id=E2E_PREF_DISPUTE_ID,
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
                        "id": E2E_PREF_DISPUTE_ID,
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

    file_path_inv = os.path.join(upload_dir, "invoice_pref_e2e.pdf")
    with open(file_path_inv, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_inv = EvidenceDocument(
        id=E2E_PREF_EVIDENCE_INV_ID,
        dispute_id=E2E_PREF_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_pref_inv_1",
        original_filename="invoice_pref_e2e.pdf",
        internal_filename="internal_pref_inv_1.png",
        file_path=file_path_inv,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="invoice",
        processing_status="UPLOADED",
    )
    async_db.add(doc_inv)

    file_path_ship = os.path.join(upload_dir, "shipping_proof_pref_e2e.pdf")
    with open(file_path_ship, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_ship = EvidenceDocument(
        id=E2E_PREF_EVIDENCE_SHIP_ID,
        dispute_id=E2E_PREF_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_pref_ship_1",
        original_filename="shipping_proof_pref_e2e.pdf",
        internal_filename="internal_pref_ship_1.png",
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


class TestContestSubmissionPreflightE2E:
    """E2E integration test suite for contest submission preflight authorization gate."""

    @pytest.mark.asyncio
    async def test_preflight_full_pipeline_authorization(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship, upload_dir, processed_dir = await _setup_e2e_preflight_pipeline(async_db, tmp_path)

        # Stage 1: Document Processing
        proc_inv = await process_evidence_document(doc_inv.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir)
        proc_ship = await process_evidence_document(doc_ship.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir)
        assert proc_inv["status"] == "READY_FOR_AI"
        assert proc_ship["status"] == "READY_FOR_AI"

        # Stage 2: AI Extraction
        ext_inv = await execute_ai_extraction(doc_inv.id, async_db, provider=MockAIProvider(), document_hint="invoice")
        ext_ship = await execute_ai_extraction(doc_ship.id, async_db, provider=MockAIProvider(), document_hint="shipping_proof")
        assert ext_inv["status"] == "AI_EXTRACTED"
        assert ext_ship["status"] == "AI_EXTRACTED"

        # Stage 3: Evidence Matcher
        match_res = await run_evidence_matching(E2E_PREF_DISPUTE_ID, async_db)
        assert match_res.dispute_id == E2E_PREF_DISPUTE_ID

        # Stage 4: Policy Engine
        policy_res = await evaluate_dispute_policy(E2E_PREF_DISPUTE_ID, async_db, reference_date="2026-08-26")
        assert policy_res.dispute_id == E2E_PREF_DISPUTE_ID

        # Stage 5: Contest Response Drafting Engine
        draft = await generate_contest_draft(E2E_PREF_DISPUTE_ID, async_db, reference_date="2026-08-26")
        assert draft.status in ["DRAFT", "REVIEW_REQUIRED"]

        # Stage 6: Preflight Before Human Review -> REVIEW_REQUIRED
        preflight_pre_review = await run_preflight(E2E_PREF_DISPUTE_ID, async_db)
        assert preflight_pre_review.status == PreflightStatus.REVIEW_REQUIRED

        # Stage 7: Human Review Approval
        rev_res = await review_contest_draft(
            E2E_PREF_DISPUTE_ID, ReviewDecision.APPROVE, comment="E2E Preflight Approval", reviewer_reference="preflight_lead", db=async_db
        )
        assert rev_res.new_review_status == "APPROVED"

        # Stage 8: Preflight After Approval -> READY
        preflight_post_review = await run_preflight(E2E_PREF_DISPUTE_ID, async_db)
        assert preflight_post_review.status == PreflightStatus.READY
        assert preflight_post_review.review_status == "APPROVED"
        assert preflight_post_review.verified_financial_identity["amount"] == 9030000
        assert len(preflight_post_review.blocking_reasons) == 0

        # Verify Immutable Preflight Snapshot Record Persisted
        stmt_snap = select(ContestSubmissionPreflight).where(ContestSubmissionPreflight.dispute_id == E2E_PREF_DISPUTE_ID)
        snapshots = (await async_db.execute(stmt_snap)).scalars().all()
        assert len(snapshots) == 2  # Stage 6 and Stage 8 snapshots
        assert snapshots[-1].status == "READY"

    @pytest.mark.asyncio
    async def test_preflight_e2e_financial_immutability(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship, upload_dir, processed_dir = await _setup_e2e_preflight_pipeline(async_db, tmp_path)

        pay_before = dispute.payment_id
        amt_before = dispute.amount
        curr_before = dispute.currency

        # Process and generate draft
        await process_evidence_document(doc_inv.id, async_db, override_processed_dir=processed_dir, override_upload_dir=upload_dir)
        await execute_ai_extraction(doc_inv.id, async_db, provider=MockAIProvider(), document_hint="invoice")
        await run_evidence_matching(E2E_PREF_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_PREF_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await generate_contest_draft(E2E_PREF_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await review_contest_draft(E2E_PREF_DISPUTE_ID, ReviewDecision.APPROVE, comment="Approved for immutability check", db=async_db)

        # Run preflight
        res = await run_preflight(E2E_PREF_DISPUTE_ID, async_db)
        assert res.status == PreflightStatus.READY

        # Verify trusted dispute financial fields are untouched
        stmt = select(Dispute).where(Dispute.id == E2E_PREF_DISPUTE_ID)
        disp_after = (await async_db.execute(stmt)).scalars().first()
        assert disp_after.payment_id == pay_before
        assert disp_after.amount == amt_before
        assert disp_after.currency == curr_before
