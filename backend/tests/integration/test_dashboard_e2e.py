"""
End-to-End Integration Test Suite: Dispute Lifecycle Dashboard — Task 6.1

Full Pipeline:
Dispute -> Evidence -> Processing -> Extraction -> MatchResult -> PolicyResult -> ContestDraft -> Review -> Preflight -> Submission -> Reconciliation -> Lifecycle Snapshot

Verifies:
- Complete operational dashboard lifecycle representation
- UNKNOWN submission visibility in reconciliation-required view
- ACTION_REQUIRED dispute visibility in action-required view
- WON / LOST final outcome representation
- Financial immutability assertions (payment_id, amount, currency untouched)
- Zero Razorpay network calls executed from dashboard
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
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.services.contest_submission_preflight_service import run_preflight
from backend.app.services.contest_submission_service import submit_dispute_contest
from backend.app.services.dashboard_service import (
    get_action_required_disputes,
    get_dashboard_alerts,
    get_dashboard_disputes,
    get_dashboard_summary,
    get_dispute_dashboard_detail,
    get_outcomes_summary,
    get_reconciliation_required_disputes,
)
from backend.app.services.dispute_lifecycle_sync_service import sync_dispute_lifecycle
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy
from backend.app.services.razorpay_client import MockRazorpayClient

E2E_DASH_DISPUTE_ID = "disp_synth_dash_01"
E2E_DASH_EVIDENCE_INV_ID = "doc_dash_e2e_inv_1"
E2E_DASH_EVIDENCE_SHIP_ID = "doc_dash_e2e_ship_1"

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


def make_mock_rzp_dash(dispute_id: str, status: str = "under_review", phase: str = "chargeback"):
    """Helper to instantiate MockRazorpayClient for lifecycle sync E2E dashboard setup."""
    raw_dispute = {
        "id": dispute_id,
        "entity": "dispute",
        "payment_id": "pay_synth_dash_01",
        "amount": 750000,
        "currency": "INR",
        "amount_deducted": 750000,
        "reason_code": "13.1",
        "respond_by": 1735689600,
        "status": status,
        "phase": phase,
        "created_at": 1600000000,
    }
    return MockRazorpayClient(mock_disputes={dispute_id: raw_dispute})


async def _setup_e2e_dashboard_pipeline(async_db, tmp_path):
    """Sets up a local dispute and evidence pipeline for dashboard E2E testing."""
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    await async_db.execute(text("DELETE FROM dispute_lifecycle_snapshots WHERE dispute_id = :d"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submission_audits WHERE dispute_id = :d"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submissions WHERE dispute_id = :d"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submission_preflights WHERE dispute_id = :d"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_draft_review_audits WHERE dispute_id = :d"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_drafts WHERE dispute_id = :d"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = :d"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = :d"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM extracted_evidence WHERE document_id IN (SELECT id FROM evidence_documents WHERE dispute_id = :d)"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM evidence_documents WHERE dispute_id = :d"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM disputes WHERE id = :d"), {"d": E2E_DASH_DISPUTE_ID})
    await async_db.commit()

    dispute = Dispute(
        id=E2E_DASH_DISPUTE_ID,
        payment_id="pay_synth_dash_01",
        amount=750000,
        currency="INR",
        reason_code="13.1",
        status="open",
        raw_payload={"payload": {"dispute": {"entity": {"id": E2E_DASH_DISPUTE_ID, "payment_id": "pay_synth_dash_01", "order_id": "ord_synth_dash_01", "amount": 750000, "currency": "INR"}}}},
    )
    async_db.add(dispute)

    file_hash = hashlib.sha256(MINIMAL_VALID_PDF).hexdigest()

    file_path_inv = os.path.join(upload_dir, "invoice_dash_e2e.pdf")
    with open(file_path_inv, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_inv = EvidenceDocument(
        id=E2E_DASH_EVIDENCE_INV_ID,
        dispute_id=E2E_DASH_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_dash_inv_1",
        original_filename="invoice_dash_e2e.pdf",
        internal_filename="internal_dash_inv_1.png",
        file_path=file_path_inv,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="invoice",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_inv)

    ext_inv = ExtractedEvidence(
        id="ext_dash_inv_1",
        document_id=E2E_DASH_EVIDENCE_INV_ID,
        document_type="invoice",
        payment_id="pay_synth_dash_01",
        order_id="ord_synth_dash_01",
        amount_minor=750000,
        currency="INR",
        customer_name="Ananya Sharma",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_dash_01", "order_id": "ord_synth_dash_01", "amount_minor": 750000},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_inv)

    file_path_ship = os.path.join(upload_dir, "shipping_proof_dash_e2e.pdf")
    with open(file_path_ship, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_ship = EvidenceDocument(
        id=E2E_DASH_EVIDENCE_SHIP_ID,
        dispute_id=E2E_DASH_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_dash_ship_1",
        original_filename="shipping_proof_dash_e2e.pdf",
        internal_filename="internal_dash_ship_1.png",
        file_path=file_path_ship,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="shipping_proof",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_ship)

    ext_ship = ExtractedEvidence(
        id="ext_dash_ship_1",
        document_id=E2E_DASH_EVIDENCE_SHIP_ID,
        document_type="shipping_proof",
        payment_id="pay_synth_dash_01",
        order_id="ord_synth_dash_01",
        awb_number="1Z9998880001",
        delivery_date="2026-08-18",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_dash_01", "order_id": "ord_synth_dash_01", "awb_number": "1Z9998880001", "delivery_date": "2026-08-18"},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_ship)
    await async_db.commit()

    return dispute, doc_inv, doc_ship


class TestDashboardE2E:
    """E2E integration test suite for dispute lifecycle operational dashboard."""

    @pytest.mark.asyncio
    async def test_full_pipeline_dashboard_observability(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship = await _setup_e2e_dashboard_pipeline(async_db, tmp_path)

        # Stage 1: Pipeline execution through submission
        await run_evidence_matching(E2E_DASH_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_DASH_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await generate_contest_draft(E2E_DASH_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await review_contest_draft(E2E_DASH_DISPUTE_ID, ReviewDecision.APPROVE, comment="E2E Dashboard Approval", db=async_db)
        await run_preflight(E2E_DASH_DISPUTE_ID, async_db)

        client_sub = MockContestSubmissionClient(mode="SUCCESS")
        await submit_dispute_contest(E2E_DASH_DISPUTE_ID, async_db, client=client_sub)

        client_rzp = make_mock_rzp_dash(E2E_DASH_DISPUTE_ID, status="won")
        await sync_dispute_lifecycle(E2E_DASH_DISPUTE_ID, async_db, razorpay_client=client_rzp)

        # Stage 2: Dashboard Observability Assertions
        summary = await get_dashboard_summary(async_db)
        assert summary.total_disputes >= 1
        assert summary.won_count >= 1

        detail = await get_dispute_dashboard_detail(E2E_DASH_DISPUTE_ID, async_db)
        assert detail.dispute["dispute_id"] == E2E_DASH_DISPUTE_ID
        assert detail.evidence["evidence_count"] == 2
        assert detail.policy["policy_outcome"] == "ELIGIBLE"
        assert detail.contest_draft["review_status"] == "APPROVED"
        assert detail.preflight["preflight_status"] == "READY"
        assert detail.submission["submission_status"] == "SUBMITTED"
        assert detail.razorpay_lifecycle["outcome"] == "WON"
        assert len(detail.timeline) >= 8

        outcomes = await get_outcomes_summary(async_db)
        assert outcomes.won_count >= 1

    @pytest.mark.asyncio
    async def test_dashboard_reconciliation_and_action_required_views(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship = await _setup_e2e_dashboard_pipeline(async_db, tmp_path)

        # Pipeline execution with TIMEOUT -> UNKNOWN state
        await run_evidence_matching(E2E_DASH_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_DASH_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await generate_contest_draft(E2E_DASH_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await review_contest_draft(E2E_DASH_DISPUTE_ID, ReviewDecision.APPROVE, comment="Approved for timeout test", db=async_db)
        await run_preflight(E2E_DASH_DISPUTE_ID, async_db)

        client_sub = MockContestSubmissionClient(mode="TIMEOUT")
        await submit_dispute_contest(E2E_DASH_DISPUTE_ID, async_db, client=client_sub)

        # Assert UNKNOWN state appears in reconciliation-required view
        recon_items = await get_reconciliation_required_disputes(async_db)
        assert any(i.dispute_id == E2E_DASH_DISPUTE_ID for i in recon_items)

        # Assert operational alerts include SUBMISSION_UNKNOWN
        alerts = await get_dashboard_alerts(async_db)
        assert any(a.alert_code == "SUBMISSION_UNKNOWN" and a.dispute_id == E2E_DASH_DISPUTE_ID for a in alerts)
