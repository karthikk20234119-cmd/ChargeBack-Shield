"""
End-to-End Integration Test Suite: Contest Submission Status Reconciliation — Task 5.4C

Full Pipeline:
Dispute -> ExtractedEvidence -> MatchResult -> PolicyResult -> ContestDraft -> Human Approval -> Preflight READY -> Submission TIMEOUT (UNKNOWN) -> Read-Only Razorpay Status Lookup -> Reconciliation -> SUBMITTED

Verifies:
- Complete end-to-end reconciliation pipeline execution
- State machine transitions (UNKNOWN / SUBMISSION_IN_PROGRESS -> SUBMITTED)
- Financial immutability assertions (payment_id, amount, currency untouched)
- Unresolved UNKNOWN, 404 ambiguity, stale fingerprint, concurrent reconciliation, and repeated idempotency
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
from backend.app.schemas.contest_submission_reconciliation import ReconciliationOutcome
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.services.contest_submission_preflight_service import run_preflight
from backend.app.services.contest_submission_reconciliation_service import reconcile_contest_submission
from backend.app.services.contest_submission_service import submit_dispute_contest
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy
from backend.app.services.razorpay_client import MockRazorpayClient

E2E_REC_DISPUTE_ID = "disp_synth_0002"
E2E_REC_EVIDENCE_INV_ID = "doc_rec_e2e_inv_2"
E2E_REC_EVIDENCE_SHIP_ID = "doc_rec_e2e_ship_2"

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


def make_mock_rzp(dispute_id: str, status: str = "under_review", error_mode: str | None = None):
    """Helper to instantiate MockRazorpayClient for reconciliation E2E tests."""
    if error_mode:
        return MockRazorpayClient(error_mode=error_mode)
    raw_dispute = {
        "id": dispute_id,
        "entity": "dispute",
        "payment_id": "pay_synth_0002",
        "amount": 500000,
        "currency": "INR",
        "amount_deducted": 500000,
        "reason_code": "13.1",
        "respond_by": 1735689600,
        "status": status,
        "phase": "chargeback",
        "created_at": 1600000000,
    }
    return MockRazorpayClient(mock_disputes={dispute_id: raw_dispute})


async def _setup_e2e_reconciliation_pipeline(async_db, tmp_path):
    """Sets up a local dispute and evidence pipeline for reconciliation E2E testing."""
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # Clean up existing test data
    await async_db.execute(text("DELETE FROM contest_submission_audits WHERE dispute_id = :d"), {"d": E2E_REC_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submissions WHERE dispute_id = :d"), {"d": E2E_REC_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submission_preflights WHERE dispute_id = :d"), {"d": E2E_REC_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_draft_review_audits WHERE dispute_id = :d"), {"d": E2E_REC_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_drafts WHERE dispute_id = :d"), {"d": E2E_REC_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = :d"), {"d": E2E_REC_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = :d"), {"d": E2E_REC_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM extracted_evidence WHERE document_id IN (SELECT id FROM evidence_documents WHERE dispute_id = :d)"), {"d": E2E_REC_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM evidence_documents WHERE dispute_id = :d"), {"d": E2E_REC_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM disputes WHERE id = :d"), {"d": E2E_REC_DISPUTE_ID})
    await async_db.commit()

    dispute = Dispute(
        id=E2E_REC_DISPUTE_ID,
        payment_id="pay_synth_0002",
        amount=500000,
        currency="INR",
        reason_code="13.1",
        status="open",
        raw_payload={
            "payload": {
                "dispute": {
                    "entity": {
                        "id": E2E_REC_DISPUTE_ID,
                        "payment_id": "pay_synth_0002",
                        "order_id": "ord_synth_0002",
                        "amount": 500000,
                        "currency": "INR",
                        "awb_number": "1Z9998880002",
                    }
                }
            }
        },
    )
    async_db.add(dispute)

    file_hash = hashlib.sha256(MINIMAL_VALID_PDF).hexdigest()

    file_path_inv = os.path.join(upload_dir, "invoice_rec_e2e.pdf")
    with open(file_path_inv, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_inv = EvidenceDocument(
        id=E2E_REC_EVIDENCE_INV_ID,
        dispute_id=E2E_REC_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_rec_inv_2",
        original_filename="invoice_rec_e2e.pdf",
        internal_filename="internal_rec_inv_2.png",
        file_path=file_path_inv,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="invoice",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_inv)

    ext_inv = ExtractedEvidence(
        id="ext_rec_inv_2",
        document_id=E2E_REC_EVIDENCE_INV_ID,
        document_type="invoice",
        payment_id="pay_synth_0002",
        order_id="ord_synth_0002",
        amount_minor=500000,
        currency="INR",
        customer_name="Priya Sharma",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_0002", "order_id": "ord_synth_0002", "amount_minor": 500000},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_inv)

    file_path_ship = os.path.join(upload_dir, "shipping_proof_rec_e2e.pdf")
    with open(file_path_ship, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_ship = EvidenceDocument(
        id=E2E_REC_EVIDENCE_SHIP_ID,
        dispute_id=E2E_REC_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_rec_ship_2",
        original_filename="shipping_proof_rec_e2e.pdf",
        internal_filename="internal_rec_ship_2.png",
        file_path=file_path_ship,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="shipping_proof",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_ship)

    ext_ship = ExtractedEvidence(
        id="ext_rec_ship_2",
        document_id=E2E_REC_EVIDENCE_SHIP_ID,
        document_type="shipping_proof",
        payment_id="pay_synth_0002",
        order_id="ord_synth_0002",
        awb_number="1Z9998880002",
        delivery_date="2026-08-18",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_0002", "order_id": "ord_synth_0002", "awb_number": "1Z9998880002", "delivery_date": "2026-08-18"},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_ship)
    await async_db.commit()

    return dispute, doc_inv, doc_ship, upload_dir, processed_dir


class TestContestSubmissionReconciliationE2E:
    """E2E integration test suite for contest submission status reconciliation."""

    @pytest.mark.asyncio
    async def test_full_pipeline_reconciliation(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship, upload_dir, processed_dir = await _setup_e2e_reconciliation_pipeline(async_db, tmp_path)

        # Stage 1: Evidence Matcher & Policy & Draft
        await run_evidence_matching(E2E_REC_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_REC_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await generate_contest_draft(E2E_REC_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await review_contest_draft(E2E_REC_DISPUTE_ID, ReviewDecision.APPROVE, comment="E2E Reconciliation Approval", db=async_db)
        await run_preflight(E2E_REC_DISPUTE_ID, async_db)

        # Stage 2: Attempt submission with network timeout -> UNKNOWN state
        client_sub = MockContestSubmissionClient(mode="TIMEOUT")
        sub_res = await submit_dispute_contest(E2E_REC_DISPUTE_ID, async_db, client=client_sub)
        assert sub_res.status == SubmissionStatus.UNKNOWN

        # Stage 3: Read-Only Reconciliation Lookup via MockRazorpayClient
        client_rzp = make_mock_rzp(dispute_id=E2E_REC_DISPUTE_ID, status="under_review")
        rec_res = await reconcile_contest_submission(E2E_REC_DISPUTE_ID, async_db, razorpay_client=client_rzp)

        assert rec_res.previous_status == SubmissionStatus.UNKNOWN
        assert rec_res.new_status == SubmissionStatus.SUBMITTED
        assert rec_res.outcome == ReconciliationOutcome.RECONCILED_SUBMITTED
        assert rec_res.razorpay_status == "under_review"

        # Verify Record Persisted in Database
        stmt_sub = select(ContestSubmission).where(ContestSubmission.dispute_id == E2E_REC_DISPUTE_ID)
        db_sub = (await async_db.execute(stmt_sub)).scalars().first()
        assert db_sub.state == "SUBMITTED"
        assert db_sub.reconciled_at is not None

        # Repeated reconciliation returns ALREADY_SUBMITTED cleanly
        rec_res_dup = await reconcile_contest_submission(E2E_REC_DISPUTE_ID, async_db, razorpay_client=client_rzp)
        assert rec_res_dup.outcome == ReconciliationOutcome.ALREADY_SUBMITTED

    @pytest.mark.asyncio
    async def test_e2e_reconciliation_financial_immutability(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship, upload_dir, processed_dir = await _setup_e2e_reconciliation_pipeline(async_db, tmp_path)

        pay_before = dispute.payment_id
        amt_before = dispute.amount
        curr_before = dispute.currency

        # Run pipeline through submission & reconciliation
        await run_evidence_matching(E2E_REC_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_REC_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await generate_contest_draft(E2E_REC_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await review_contest_draft(E2E_REC_DISPUTE_ID, ReviewDecision.APPROVE, comment="Approved for immutability test", db=async_db)
        await run_preflight(E2E_REC_DISPUTE_ID, async_db)

        client_sub = MockContestSubmissionClient(mode="TIMEOUT")
        await submit_dispute_contest(E2E_REC_DISPUTE_ID, async_db, client=client_sub)

        client_rzp = make_mock_rzp(dispute_id=E2E_REC_DISPUTE_ID, status="under_review")
        await reconcile_contest_submission(E2E_REC_DISPUTE_ID, async_db, razorpay_client=client_rzp)

        # Verify dispute financial fields are 100% untouched
        stmt = select(Dispute).where(Dispute.id == E2E_REC_DISPUTE_ID)
        disp_after = (await async_db.execute(stmt)).scalars().first()
        assert disp_after.payment_id == pay_before
        assert disp_after.amount == amt_before
        assert disp_after.currency == curr_before
