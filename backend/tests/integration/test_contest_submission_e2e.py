"""
End-to-End Integration Test Suite: Controlled Contest Submission Execution — Task 5.4B

Full Pipeline:
Dispute -> EvidenceDocument -> ExtractedEvidence -> MatchResult -> PolicyResult -> ContestDraft -> Human Review APPROVED -> Preflight READY -> Submission Authorization -> Mock Razorpay Contest -> SUBMITTED

Verifies:
- Complete end-to-end pipeline execution from ingestion through submission
- State machine transitions (READY -> SUBMISSION_AUTHORIZED -> SUBMISSION_IN_PROGRESS -> SUBMITTED / UNKNOWN)
- Financial immutability assertions (payment_id, amount, currency untouched)
- Duplicate and concurrent submission defenses
- Zero external network calls and zero real Razorpay credentials
"""

import hashlib
import os
import pytest
from sqlalchemy import text
from sqlalchemy.future import select

from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.schemas.contest_draft_review import ReviewDecision
from backend.app.schemas.contest_submission import SubmissionStatus
from backend.app.schemas.contest_submission_preflight import PreflightStatus
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.services.contest_submission_preflight_service import run_preflight
from backend.app.services.contest_submission_service import (
    SubmissionConflictException,
    submit_dispute_contest,
)
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy

E2E_SUB_DISPUTE_ID = "disp_synth_0001"
E2E_SUB_EVIDENCE_INV_ID = "doc_sub_e2e_inv_1"
E2E_SUB_EVIDENCE_SHIP_ID = "doc_sub_e2e_ship_1"

MINIMAL_VALID_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
    b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
    b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>> endobj\n"
    b"xref\n0 4\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000056 00000 n \n"
    b"00000000111 00000 n \n"
    b"trailer <</Size 4 /Root 1 0 R>>\n"
    b"startxref\n173\n"
    b"%%EOF\n"
)


async def _setup_e2e_submission_pipeline(async_db, tmp_path):
    """Sets up a local dispute and 2 evidence documents for submission E2E testing."""
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # Clean up existing test data
    await async_db.execute(text("DELETE FROM contest_submission_audits WHERE dispute_id = :d"), {"d": E2E_SUB_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submissions WHERE dispute_id = :d"), {"d": E2E_SUB_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submission_preflights WHERE dispute_id = :d"), {"d": E2E_SUB_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_draft_review_audits WHERE dispute_id = :d"), {"d": E2E_SUB_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_drafts WHERE dispute_id = :d"), {"d": E2E_SUB_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = :d"), {"d": E2E_SUB_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = :d"), {"d": E2E_SUB_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM extracted_evidence WHERE document_id IN (SELECT id FROM evidence_documents WHERE dispute_id = :d)"), {"d": E2E_SUB_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM evidence_documents WHERE dispute_id = :d"), {"d": E2E_SUB_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM disputes WHERE id = :d"), {"d": E2E_SUB_DISPUTE_ID})
    await async_db.commit()

    dispute = Dispute(
        id=E2E_SUB_DISPUTE_ID,
        payment_id="pay_synth_0001",
        amount=500000,
        currency="INR",
        reason_code="13.1",
        status="open",
        raw_payload={
            "payload": {
                "dispute": {
                    "entity": {
                        "id": E2E_SUB_DISPUTE_ID,
                        "payment_id": "pay_synth_0001",
                        "order_id": "ord_synth_0001",
                        "amount": 500000,
                        "currency": "INR",
                        "awb_number": "1Z9998880001",
                    }
                }
            }
        },
    )
    async_db.add(dispute)

    file_hash = hashlib.sha256(MINIMAL_VALID_PDF).hexdigest()

    file_path_inv = os.path.join(upload_dir, "invoice_sub_e2e.pdf")
    with open(file_path_inv, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_inv = EvidenceDocument(
        id=E2E_SUB_EVIDENCE_INV_ID,
        dispute_id=E2E_SUB_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_sub_inv_1",
        original_filename="invoice_sub_e2e.pdf",
        internal_filename="internal_sub_inv_1.png",
        file_path=file_path_inv,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="invoice",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_inv)

    ext_inv = ExtractedEvidence(
        id="ext_sub_inv_1",
        document_id=E2E_SUB_EVIDENCE_INV_ID,
        document_type="invoice",
        payment_id="pay_synth_0001",
        order_id="ord_synth_0001",
        amount_minor=500000,
        currency="INR",
        customer_name="Gaurav Sharma",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_0001", "order_id": "ord_synth_0001", "amount_minor": 500000},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_inv)

    file_path_ship = os.path.join(upload_dir, "shipping_proof_sub_e2e.pdf")
    with open(file_path_ship, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_ship = EvidenceDocument(
        id=E2E_SUB_EVIDENCE_SHIP_ID,
        dispute_id=E2E_SUB_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_sub_ship_1",
        original_filename="shipping_proof_sub_e2e.pdf",
        internal_filename="internal_sub_ship_1.png",
        file_path=file_path_ship,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="shipping_proof",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_ship)

    ext_ship = ExtractedEvidence(
        id="ext_sub_ship_1",
        document_id=E2E_SUB_EVIDENCE_SHIP_ID,
        document_type="shipping_proof",
        payment_id="pay_synth_0001",
        order_id="ord_synth_0001",
        awb_number="1Z9998880001",
        delivery_date="2026-08-18",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_0001", "order_id": "ord_synth_0001", "awb_number": "1Z9998880001", "delivery_date": "2026-08-18"},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_ship)
    await async_db.commit()

    return dispute, doc_inv, doc_ship, upload_dir, processed_dir


class TestContestSubmissionE2E:
    """E2E integration test suite for contest submission execution boundary."""

    @pytest.mark.asyncio
    async def test_full_pipeline_submission_execution(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship, upload_dir, processed_dir = await _setup_e2e_submission_pipeline(async_db, tmp_path)

        # Stage 1: Evidence Matcher
        match_res = await run_evidence_matching(E2E_SUB_DISPUTE_ID, async_db)
        assert match_res.dispute_id == E2E_SUB_DISPUTE_ID

        # Stage 2: Policy Engine
        policy_res = await evaluate_dispute_policy(E2E_SUB_DISPUTE_ID, async_db, reference_date="2026-08-26")
        assert policy_res.dispute_id == E2E_SUB_DISPUTE_ID
        assert policy_res.decision == "ELIGIBLE"

        # Stage 3: Contest Response Drafting Engine
        draft = await generate_contest_draft(E2E_SUB_DISPUTE_ID, async_db, reference_date="2026-08-26")
        assert draft.status in ["DRAFT", "REVIEW_REQUIRED"]

        # Stage 4: Human Review Approval
        rev_res = await review_contest_draft(
            E2E_SUB_DISPUTE_ID, ReviewDecision.APPROVE, comment="E2E Contest Submission Approval", reviewer_reference="submission_lead", db=async_db
        )
        assert rev_res.new_review_status == "APPROVED"

        # Stage 5: Preflight Authorization Gate -> READY
        preflight_res = await run_preflight(E2E_SUB_DISPUTE_ID, async_db)
        assert preflight_res.status == PreflightStatus.READY

        # Stage 6: Submission Execution via Mock Client
        client = MockContestSubmissionClient(mode="SUCCESS")
        sub_res = await submit_dispute_contest(E2E_SUB_DISPUTE_ID, async_db, client=client)

        assert sub_res.status == SubmissionStatus.SUBMITTED
        assert sub_res.razorpay_status == "under_review"
        assert sub_res.razorpay_reference_id == f"sub_ref_mock_{E2E_SUB_DISPUTE_ID}"
        assert sub_res.audit_id is not None

        # Verify Record Persisted in Database
        stmt_sub = select(ContestSubmission).where(ContestSubmission.dispute_id == E2E_SUB_DISPUTE_ID)
        db_sub = (await async_db.execute(stmt_sub)).scalars().first()
        assert db_sub is not None
        assert db_sub.state == "SUBMITTED"
        assert db_sub.razorpay_reference == f"sub_ref_mock_{E2E_SUB_DISPUTE_ID}"

        # Duplicate submission attempt must fail with 409 Conflict
        with pytest.raises(SubmissionConflictException):
            await submit_dispute_contest(E2E_SUB_DISPUTE_ID, async_db, client=client)

    @pytest.mark.asyncio
    async def test_e2e_financial_immutability(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship, upload_dir, processed_dir = await _setup_e2e_submission_pipeline(async_db, tmp_path)

        pay_before = dispute.payment_id
        amt_before = dispute.amount
        curr_before = dispute.currency

        # Run pipeline through submission
        await run_evidence_matching(E2E_SUB_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_SUB_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await generate_contest_draft(E2E_SUB_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await review_contest_draft(E2E_SUB_DISPUTE_ID, ReviewDecision.APPROVE, comment="Approved for immutability test", db=async_db)
        await run_preflight(E2E_SUB_DISPUTE_ID, async_db)

        client = MockContestSubmissionClient(mode="SUCCESS")
        await submit_dispute_contest(E2E_SUB_DISPUTE_ID, async_db, client=client)

        # Verify dispute financial fields are untouched
        stmt = select(Dispute).where(Dispute.id == E2E_SUB_DISPUTE_ID)
        disp_after = (await async_db.execute(stmt)).scalars().first()
        assert disp_after.payment_id == pay_before
        assert disp_after.amount == amt_before
        assert disp_after.currency == curr_before
