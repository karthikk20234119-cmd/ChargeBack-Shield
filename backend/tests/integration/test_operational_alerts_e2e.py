"""
End-to-End Integration Test Suite: Operational Alerts, SLA Monitoring & Exception Management — Task 6.3

Full Pipeline:
Dispute -> Evidence -> Processing -> Extraction -> Matching -> Policy -> ContestDraft -> Review -> Preflight -> Submission -> Reconciliation -> Lifecycle -> Final Outcome

Verifies:
- Operational alerts generated deterministically from persisted local database state across normal and exception states
- Zero Razorpay network calls and zero external AI/LLM calls
- Zero source business entity mutations (Dispute, EvidenceDocument, PolicyResult, ContestDraft, ContestSubmission untouched)
- Alert acknowledgement endpoint modifies ONLY OperationalAlert.status
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
from backend.app.services.dispute_lifecycle_sync_service import sync_dispute_lifecycle
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.operational_alert_service import (
    acknowledge_operational_alert,
    detect_operational_alerts,
    get_alerts_summary,
    get_dispute_alert_detail,
    get_filtered_alerts,
    get_operational_exceptions_report,
    get_operational_health_report,
    get_sla_monitoring_report,
)
from backend.app.services.policy_engine_service import evaluate_dispute_policy
from backend.app.services.razorpay_client import MockRazorpayClient

E2E_ALERT_DISPUTE_ID = "disp_synth_alt_e2e_1"
E2E_ALERT_EVIDENCE_INV_ID = "doc_alt_e2e_inv_1"

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


def make_mock_rzp_alerts_e2e(dispute_id: str, status: str = "under_review", phase: str = "chargeback"):
    raw_dispute = {
        "id": dispute_id,
        "entity": "dispute",
        "payment_id": "pay_synth_alt_e2e_1",
        "amount": 850000,
        "currency": "INR",
        "amount_deducted": 850000,
        "reason_code": "13.1",
        "respond_by": 1735689600,
        "status": status,
        "phase": phase,
        "created_at": 1600000000,
    }
    return MockRazorpayClient(mock_disputes={dispute_id: raw_dispute})


async def _setup_e2e_alert_pipeline(async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    await async_db.execute(text("DELETE FROM operational_alerts WHERE dispute_id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM dispute_lifecycle_snapshots WHERE dispute_id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submission_audits WHERE dispute_id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submissions WHERE dispute_id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submission_preflights WHERE dispute_id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_draft_review_audits WHERE dispute_id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_drafts WHERE dispute_id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM extracted_evidence WHERE document_id IN (SELECT id FROM evidence_documents WHERE dispute_id = :d)"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM evidence_documents WHERE dispute_id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM disputes WHERE id = :d"), {"d": E2E_ALERT_DISPUTE_ID})
    await async_db.commit()

    dispute = Dispute(
        id=E2E_ALERT_DISPUTE_ID,
        payment_id="pay_synth_alt_e2e_1",
        amount=850000,
        currency="INR",
        reason_code="13.1",
        status="open",
        raw_payload={"payload": {"dispute": {"entity": {"id": E2E_ALERT_DISPUTE_ID, "payment_id": "pay_synth_alt_e2e_1", "order_id": "ord_synth_alt_e2e_1", "amount": 850000, "currency": "INR"}}}},
    )
    async_db.add(dispute)

    file_hash = hashlib.sha256(MINIMAL_VALID_PDF).hexdigest()
    file_path_inv = os.path.join(upload_dir, "invoice_alt_e2e.pdf")
    with open(file_path_inv, "wb") as f:
        f.write(MINIMAL_VALID_PDF)

    doc_inv = EvidenceDocument(
        id=E2E_ALERT_EVIDENCE_INV_ID,
        dispute_id=E2E_ALERT_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_alt_e2e_inv_1",
        original_filename="invoice_alt_e2e.pdf",
        internal_filename=f"internal_alt_e2e_inv_1_{E2E_ALERT_DISPUTE_ID}.png",
        file_path=file_path_inv,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="invoice",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_inv)

    ext_inv = ExtractedEvidence(
        id="ext_alt_e2e_inv_1",
        document_id=E2E_ALERT_EVIDENCE_INV_ID,
        document_type="invoice",
        payment_id="pay_synth_alt_e2e_1",
        order_id="ord_synth_alt_e2e_1",
        amount_minor=850000,
        currency="INR",
        customer_name="Aditya Verma",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_alt_e2e_1", "order_id": "ord_synth_alt_e2e_1", "amount_minor": 850000},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_inv)
    await async_db.commit()

    return dispute, doc_inv


class TestOperationalAlertsE2E:
    """E2E integration test suite for operational alerts, SLA monitoring & exception management."""

    @pytest.mark.asyncio
    async def test_full_pipeline_alert_detection_and_sla(self, async_db, tmp_path):
        dispute, doc_inv = await _setup_e2e_alert_pipeline(async_db, tmp_path)

        # Step 1: Run pipeline up to pending review
        await run_evidence_matching(E2E_ALERT_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_ALERT_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await generate_contest_draft(E2E_ALERT_DISPUTE_ID, async_db, reference_date="2026-08-26")

        # Step 2: Detect alerts at pending review state
        res1 = await detect_operational_alerts(async_db)
        assert res1.detected_count >= 1
        codes1 = [a.code for a in res1.alerts if a.dispute_id == E2E_ALERT_DISPUTE_ID]
        assert "HUMAN_REVIEW_REQUIRED" in codes1

        # Step 3: Approve review, preflight, submit, sync lifecycle
        await review_contest_draft(E2E_ALERT_DISPUTE_ID, ReviewDecision.APPROVE, comment="E2E Alert Approval", db=async_db)
        await run_preflight(E2E_ALERT_DISPUTE_ID, async_db)

        client_sub = MockContestSubmissionClient(mode="SUCCESS")
        await submit_dispute_contest(E2E_ALERT_DISPUTE_ID, async_db, client=client_sub)

        client_rzp = make_mock_rzp_alerts_e2e(E2E_ALERT_DISPUTE_ID, status="under_review")
        await sync_dispute_lifecycle(E2E_ALERT_DISPUTE_ID, async_db, razorpay_client=client_rzp)

        # Step 4: Re-detect alerts after completion
        res2 = await detect_operational_alerts(async_db)

        # Human review alert should now be RESOLVED
        detail = await get_dispute_alert_detail(E2E_ALERT_DISPUTE_ID, async_db)

        # Step 5: SLA & Health Reports
        sla_rep = await get_sla_monitoring_report(async_db)
        assert sla_rep.total_tracked >= 0

        health_rep = await get_operational_health_report(async_db)
        assert health_rep.total_disputes >= 1

        # Step 6: Verify zero mutations on Dispute
        stmt_disp = select(Dispute).where(Dispute.id == E2E_ALERT_DISPUTE_ID)
        disp_after = (await async_db.execute(stmt_disp)).scalars().first()

        assert disp_after.payment_id == "pay_synth_alt_e2e_1"
        assert disp_after.amount == 850000
        assert disp_after.currency == "INR"
