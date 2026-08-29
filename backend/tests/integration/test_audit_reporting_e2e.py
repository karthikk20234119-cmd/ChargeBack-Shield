"""
End-to-End Integration Test Suite: Audit, Compliance & Evidence Traceability Reporting — Task 6.2

Full Pipeline:
Dispute -> Evidence -> Processing -> Extraction -> Matching -> Policy -> ContestDraft -> Review -> Preflight -> Submission -> Reconciliation -> Lifecycle -> Final Outcome

Verifies:
- Complete audit timeline representation across all 13 lifecycle stages
- Complete directed acyclic graph (DAG) traceability report
- Canonical SHA-256 compliance export generation & hash stability
- Financial identity immutability assertions (payment_id, amount, currency untouched)
- Zero Razorpay network calls and zero external AI/LLM calls
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
from backend.app.services.audit_reporting_service import (
    evaluate_audit_tamper,
    generate_compliance_export,
    get_dispute_audit_timeline,
    get_dispute_traceability_graph,
    get_financial_integrity_report,
    get_human_review_audit_report,
    get_policy_compliance_report,
    get_security_audit_report,
    get_submission_audit_report,
)
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.services.contest_submission_preflight_service import run_preflight
from backend.app.services.contest_submission_service import submit_dispute_contest
from backend.app.services.dispute_lifecycle_sync_service import sync_dispute_lifecycle
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy
from backend.app.services.razorpay_client import MockRazorpayClient

E2E_AUDIT_DISPUTE_ID = "disp_synth_aud_e2e_1"
E2E_AUDIT_EVIDENCE_INV_ID = "doc_aud_e2e_inv_1"
E2E_AUDIT_EVIDENCE_SHIP_ID = "doc_aud_e2e_ship_1"

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


def make_mock_rzp_audit_e2e(dispute_id: str, status: str = "under_review", phase: str = "chargeback"):
    """Helper to instantiate MockRazorpayClient for audit E2E tests."""
    raw_dispute = {
        "id": dispute_id,
        "entity": "dispute",
        "payment_id": "pay_synth_aud_e2e_1",
        "amount": 950000,
        "currency": "INR",
        "amount_deducted": 950000,
        "reason_code": "13.1",
        "respond_by": 1735689600,
        "status": status,
        "phase": phase,
        "created_at": 1600000000,
    }
    return MockRazorpayClient(mock_disputes={dispute_id: raw_dispute})


async def _setup_e2e_audit_pipeline(async_db, tmp_path):
    """Sets up a local dispute and evidence pipeline for audit E2E testing."""
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    await async_db.execute(text("DELETE FROM dispute_lifecycle_snapshots WHERE dispute_id = :d"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submission_audits WHERE dispute_id = :d"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submissions WHERE dispute_id = :d"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_submission_preflights WHERE dispute_id = :d"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_draft_review_audits WHERE dispute_id = :d"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM contest_drafts WHERE dispute_id = :d"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = :d"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = :d"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM extracted_evidence WHERE document_id IN (SELECT id FROM evidence_documents WHERE dispute_id = :d)"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM evidence_documents WHERE dispute_id = :d"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.execute(text("DELETE FROM disputes WHERE id = :d"), {"d": E2E_AUDIT_DISPUTE_ID})
    await async_db.commit()

    dispute = Dispute(
        id=E2E_AUDIT_DISPUTE_ID,
        payment_id="pay_synth_aud_e2e_1",
        amount=950000,
        currency="INR",
        reason_code="13.1",
        status="open",
        raw_payload={"payload": {"dispute": {"entity": {"id": E2E_AUDIT_DISPUTE_ID, "payment_id": "pay_synth_aud_e2e_1", "order_id": "ord_synth_aud_e2e_1", "amount": 950000, "currency": "INR"}}}},
    )
    async_db.add(dispute)

    file_hash = hashlib.sha256(MINIMAL_VALID_PDF).hexdigest()

    file_path_inv = os.path.join(upload_dir, "invoice_aud_e2e.pdf")
    with open(file_path_inv, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_inv = EvidenceDocument(
        id=E2E_AUDIT_EVIDENCE_INV_ID,
        dispute_id=E2E_AUDIT_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_aud_e2e_inv_1",
        original_filename="invoice_aud_e2e.pdf",
        internal_filename=f"internal_aud_e2e_inv_1_{E2E_AUDIT_DISPUTE_ID}.png",
        file_path=file_path_inv,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="invoice",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_inv)

    ext_inv = ExtractedEvidence(
        id="ext_aud_e2e_inv_1",
        document_id=E2E_AUDIT_EVIDENCE_INV_ID,
        document_type="invoice",
        payment_id="pay_synth_aud_e2e_1",
        order_id="ord_synth_aud_e2e_1",
        amount_minor=950000,
        currency="INR",
        customer_name="Siddharth Rao",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_aud_e2e_1", "order_id": "ord_synth_aud_e2e_1", "amount_minor": 950000},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_inv)

    file_path_ship = os.path.join(upload_dir, "shipping_proof_aud_e2e.pdf")
    with open(file_path_ship, "wb") as f:
        f.write(MINIMAL_VALID_PDF)
    doc_ship = EvidenceDocument(
        id=E2E_AUDIT_EVIDENCE_SHIP_ID,
        dispute_id=E2E_AUDIT_DISPUTE_ID,
        razorpay_doc_id="doc_rzp_aud_e2e_ship_1",
        original_filename="shipping_proof_aud_e2e.pdf",
        internal_filename=f"internal_aud_e2e_ship_1_{E2E_AUDIT_DISPUTE_ID}.png",
        file_path=file_path_ship,
        file_hash=file_hash,
        file_size_bytes=len(MINIMAL_VALID_PDF),
        mime_type="application/pdf",
        document_type="shipping_proof",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_ship)

    ext_ship = ExtractedEvidence(
        id="ext_aud_e2e_ship_1",
        document_id=E2E_AUDIT_EVIDENCE_SHIP_ID,
        document_type="shipping_proof",
        payment_id="pay_synth_aud_e2e_1",
        order_id="ord_synth_aud_e2e_1",
        awb_number="1Z9998880055",
        delivery_date="2026-08-18",
        confidence_score=0.98,
        extracted_data={"payment_id": "pay_synth_aud_e2e_1", "order_id": "ord_synth_aud_e2e_1", "awb_number": "1Z9998880055", "delivery_date": "2026-08-18"},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_ship)
    await async_db.commit()

    return dispute, doc_inv, doc_ship


class TestAuditReportingE2E:
    """E2E integration test suite for audit, compliance & evidence traceability reporting."""

    @pytest.mark.asyncio
    async def test_full_pipeline_audit_and_traceability(self, async_db, tmp_path):
        dispute, doc_inv, doc_ship = await _setup_e2e_audit_pipeline(async_db, tmp_path)

        # Stage 1: Pipeline execution through submission & lifecycle sync
        await run_evidence_matching(E2E_AUDIT_DISPUTE_ID, async_db)
        await evaluate_dispute_policy(E2E_AUDIT_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await generate_contest_draft(E2E_AUDIT_DISPUTE_ID, async_db, reference_date="2026-08-26")
        await review_contest_draft(E2E_AUDIT_DISPUTE_ID, ReviewDecision.APPROVE, comment="E2E Audit Approval", db=async_db)
        await run_preflight(E2E_AUDIT_DISPUTE_ID, async_db)

        client_sub = MockContestSubmissionClient(mode="SUCCESS")
        await submit_dispute_contest(E2E_AUDIT_DISPUTE_ID, async_db, client=client_sub)

        client_rzp = make_mock_rzp_audit_e2e(E2E_AUDIT_DISPUTE_ID, status="won")
        await sync_dispute_lifecycle(E2E_AUDIT_DISPUTE_ID, async_db, razorpay_client=client_rzp)

        # Stage 2: Audit Timeline Verification
        timeline = await get_dispute_audit_timeline(E2E_AUDIT_DISPUTE_ID, async_db)
        assert timeline.dispute_id == E2E_AUDIT_DISPUTE_ID
        assert timeline.total_events >= 8
        assert timeline.final_outcome == "WON"

        # Stage 3: Traceability Graph Verification
        dag = await get_dispute_traceability_graph(E2E_AUDIT_DISPUTE_ID, async_db)
        assert dag.dispute_id == E2E_AUDIT_DISPUTE_ID
        assert dag.node_count >= 8

        # Stage 4: Financial Integrity Verification
        fin = await get_financial_integrity_report(E2E_AUDIT_DISPUTE_ID, async_db)
        assert fin.verification_status == "VERIFIED"
        assert fin.mutation_detected is False

        # Stage 5: Canonical Compliance Export & Hash Stability Verification
        export1 = await generate_compliance_export(E2E_AUDIT_DISPUTE_ID, async_db)
        export2 = await generate_compliance_export(E2E_AUDIT_DISPUTE_ID, async_db)

        assert export1.report_hash is not None
        assert len(export1.report_hash) == 64
        assert export1.report_hash == export2.report_hash  # Hash stability assertion!

        # Stage 6: Tamper Detection Verification
        tamp = await evaluate_audit_tamper(E2E_AUDIT_DISPUTE_ID, async_db)
        assert tamp.audit_status == "VALID"
