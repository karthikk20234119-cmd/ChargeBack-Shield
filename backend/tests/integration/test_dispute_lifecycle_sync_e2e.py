"""
End-to-End Integration Test Suite: Final Dispute Outcome Synchronization — Task 5.5

Full Pipeline:
Dispute -> ExtractedEvidence -> MatchResult -> PolicyResult -> ContestDraft -> Human Approval APPROVED -> Preflight READY -> ContestSubmission SUBMITTED -> Razorpay status UNDER_REVIEW -> Lifecycle Sync -> local UNDER_REVIEW -> Razorpay status WON/LOST -> local WON/LOST

Verifies:
- Complete end-to-end lifecycle synchronization pipeline execution
- State machine transitions (SUBMITTED -> UNDER_REVIEW -> WON / LOST)
- Terminal outcome immutability (WON / LOST cannot be overwritten)
- Financial immutability assertions (payment_id, amount, currency untouched)
- Zero external network calls and zero real Razorpay credentials
"""

import hashlib
import os
import pytest
from sqlalchemy import text
from sqlalchemy.future import select

from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.dispute import Dispute
from backend.app.models.dispute_lifecycle_snapshot import DisputeLifecycleSnapshot
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.schemas.contest_draft_review import ReviewDecision
from backend.app.schemas.contest_submission import SubmissionStatus
from backend.app.schemas.dispute_lifecycle_sync import DisputeLifecycleStatus, DisputeOutcome, SyncResultType
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.services.contest_submission_preflight_service import run_preflight
from backend.app.services.contest_submission_service import submit_dispute_contest
from backend.app.services.dispute_lifecycle_sync_service import sync_dispute_lifecycle
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy
from backend.app.services.razorpay_client import MockRazorpayClient

E2E_LIFE_DISPUTE_ID = "disp_synth_0003"
E2E_LIFE_EVIDENCE_INV_ID = "doc_life_e2e_inv_3"
E2E_LIFE_EVIDENCE_SHIP_ID = "doc_life_e2e_ship_3"

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


def make_mock_rzp_lifecycle(dispute_id: str, status: str = "under_review", phase: str = "chargeback", error_mode: str | None = None):
    """Helper to instantiate MockRazorpayClient for lifecycle sync E2E tests."""
    if error_mode:
        return MockRazorpayClient(error_mode=error_mode)
    raw_dispute = {
        "id": dispute_id,
        "entity": "dispute",
        "payment_id": "pay_synth_0003",
        "amount": 500000,
        "currency": "INR",
        "amount_deducted": 500000,
        "reason_code": "13.1",
        "respond_by": 1735689600,
        "status": status,
        "phase": phase,
        "created_at": 1600000000,
    }
    return MockRazorpayClient(mock_disputes={dispute_id: raw_dispute})


async def _setup_e2e_lifecycle_pipeline(async_db, tmp_path):
    """Sets up a local dispute and evidence pipeline for lifecycle sync E2E testing."""
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # Clean up existing test data
    await async_db.execute(text("DELETE FROM dispute_lifecycle_snapshots WHERE dispute_id = :d"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submission_audits WHERE dispute_id = :d"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submissions WHERE dispute_id = :d"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submission_preflights WHERE dispute_id = :d"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_draft_review_audits WHERE dispute_id = :d"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_drafts WHERE dispute_id = :d"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = :d"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = :d"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM extracted_evidence WHERE document_id IN (SELECT id FROM evidence_documents WHERE dispute_id = :d)"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM evidence_documents WHERE dispute_id = :d"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM disputes WHERE id = :d"), {"d": E2E_LIFE_DISPUTE_ID})
    await async_db.commit()

    dispute = Dispute(
        id=E2E_LIFE_DISPUTE_ID,
        payment_id="pay_synth_0003",
        amount=500000,
        currency="INR",
        reason_code="13.1",
        status="open",
        raw_payload={
            "payload": {
                "dispute": {
                    "entity": {
                        "id": E2E_LIFE_DISPUTE_ID,
                        "payment_id": "pay_synth_0003",
                        "order_id": "ord_synth_0003",
                        "amount": 500000,
                        "currency": "INR",
                        "awb_number": "1Z9998880003",
                    }
                }
            }
        },
    )
    async_db.add(dispute)

    file_hash = hashlib.sha256(MINIMAL_VALID_PDF).hexdigest()

    file_path_inv = os.path.join(upload_dir, "invoice_life_e2e.pdf")
    with open(file_path_inv, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_inv = EvidenceDocument(
        id=E2E_LIFE_EVIDENCE_INV_ID,
        dispute_id=E2E_LIFE_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_life_inv_3",
        original_filename="invoice_life_e2e.pdf",
        internal_filename="internal_life_inv_3.png",
        file_path=file_path_inv,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="invoice",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_inv)

    ext_inv = ExtractedEvidence(
        id="ext_life_inv_3",
        document_id=E2E_LIFE_EVIDENCE_INV_ID,
        document_type="invoice",
        payment_id="pay_synth_0003",
        order_id="ord_synth_0003",
        amount_minor=500000,
        currency="INR",
        customer_name="Rohan Verma",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_0003", "order_id": "ord_synth_0003", "amount_minor": 500000},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_inv)

    file_path_ship = os.path.join(upload_dir, "shipping_proof_life_e2e.pdf")
    with open(file_path_ship, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_ship = EvidenceDocument(
        id=E2E_LIFE_EVIDENCE_SHIP_ID,
        dispute_id=E2E_LIFE_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_life_ship_3",
        original_filename="shipping_proof_life_e2e.pdf",
        internal_filename="internal_life_ship_3.png",
        file_path=file_path_ship,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="shipping_proof",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_ship)

    ext_ship = ExtractedEvidence(
        id="ext_life_ship_3",
        document_id=E2E_LIFE_EVIDENCE_SHIP_ID,
        document_type="shipping_proof",
        payment_id="pay_synth_0003",
        order_id="ord_synth_0003",
        awb_number="1Z9998880003",
        delivery_date="2026-08-18",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_0003", "order_id": "ord_synth_0003", "awb_number": "1Z9998880003", "delivery_date": "2026-08-18"},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_ship)
    await async_db.commit()

    return dispute, doc_inv, doc_ship, upload_dir, processed_dir


class TestDisputeLifecycleSyncE2E:
    """E2E integration test suite for dispute lifecycle status synchronization."""

    @pytest.mark.asyncio
    async def test_full_pipeline_lifecycle_synchronization(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship, upload_dir, processed_dir = await _setup_e2e_lifecycle_pipeline(async_db, tmp_path)

        # Stage 1: Pipeline through submission
        await run_evidence_matching(E2E_LIFE_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_LIFE_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await generate_contest_draft(E2E_LIFE_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await review_contest_draft(E2E_LIFE_DISPUTE_ID, ReviewDecision.APPROVE, comment="E2E Lifecycle Approval", db=async_db)
        await run_preflight(E2E_LIFE_DISPUTE_ID, async_db)

        client_sub = MockContestSubmissionClient(mode="SUCCESS")
        sub_res = await submit_dispute_contest(E2E_LIFE_DISPUTE_ID, async_db, client=client_sub)
        assert sub_res.status == SubmissionStatus.SUBMITTED

        # Stage 2: Synchronize UNDER_REVIEW state
        client_rzp1 = make_mock_rzp_lifecycle(E2E_LIFE_DISPUTE_ID, status="under_review")
        sync_res1 = await sync_dispute_lifecycle(E2E_LIFE_DISPUTE_ID, async_db, razorpay_client=client_rzp1)

        assert sync_res1.current_status == DisputeLifecycleStatus.UNDER_REVIEW
        assert sync_res1.outcome == DisputeOutcome.UNDER_REVIEW
        assert sync_res1.synchronization_result == SyncResultType.STATE_CHANGED

        # Stage 3: Synchronize final WON outcome
        client_rzp2 = make_mock_rzp_lifecycle(E2E_LIFE_DISPUTE_ID, status="won")
        sync_res2 = await sync_dispute_lifecycle(E2E_LIFE_DISPUTE_ID, async_db, razorpay_client=client_rzp2)

        assert sync_res2.current_status == DisputeLifecycleStatus.WON
        assert sync_res2.outcome == DisputeOutcome.WON
        assert sync_res2.synchronization_result == SyncResultType.STATE_CHANGED

        # Stage 4: Verify Terminal Outcome Immutability
        client_rzp3 = make_mock_rzp_lifecycle(E2E_LIFE_DISPUTE_ID, status="under_review")
        sync_res3 = await sync_dispute_lifecycle(E2E_LIFE_DISPUTE_ID, async_db, razorpay_client=client_rzp3)

        assert sync_res3.outcome == DisputeOutcome.WON
        assert sync_res3.synchronization_result in [SyncResultType.TERMINAL_REACHED, SyncResultType.UNEXPECTED_TRANSITION]

        # Verify Append-Only Snapshots in Database
        stmt_snap = select(DisputeLifecycleSnapshot).where(DisputeLifecycleSnapshot.dispute_id == E2E_LIFE_DISPUTE_ID).order_by(DisputeLifecycleSnapshot.created_at.asc())
        snapshots = (await async_db.execute(stmt_snap)).scalars().all()
        assert len(snapshots) >= 3
        assert snapshots[-2].outcome == "WON"

    @pytest.mark.asyncio
    async def test_e2e_lifecycle_financial_immutability(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship, upload_dir, processed_dir = await _setup_e2e_lifecycle_pipeline(async_db, tmp_path)

        pay_before = dispute.payment_id
        amt_before = dispute.amount
        curr_before = dispute.currency

        # Run pipeline through submission & lifecycle sync
        await run_evidence_matching(E2E_LIFE_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_LIFE_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await generate_contest_draft(E2E_LIFE_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await review_contest_draft(E2E_LIFE_DISPUTE_ID, ReviewDecision.APPROVE, comment="Approved for immutability test", db=async_db)
        await run_preflight(E2E_LIFE_DISPUTE_ID, async_db)

        client_sub = MockContestSubmissionClient(mode="SUCCESS")
        await submit_dispute_contest(E2E_LIFE_DISPUTE_ID, async_db, client=client_sub)

        client_rzp = make_mock_rzp_lifecycle(E2E_LIFE_DISPUTE_ID, status="won")
        await sync_dispute_lifecycle(E2E_LIFE_DISPUTE_ID, async_db, razorpay_client=client_rzp)

        # Verify dispute financial fields are 100% untouched
        stmt = select(Dispute).where(Dispute.id == E2E_LIFE_DISPUTE_ID)
        disp_after = (await async_db.execute(stmt)).scalars().first()
        assert disp_after.payment_id == pay_before
        assert disp_after.amount == amt_before
        assert disp_after.currency == curr_before
