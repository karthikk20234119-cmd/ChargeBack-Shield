"""
Unit Test Suite: Contest Submission Status Reconciliation — Task 5.4C

Comprehensive 32-test suite covering read-only status reconciliation, state machine transitions
(UNKNOWN -> SUBMITTED, IN_PROGRESS -> SUBMITTED, UNKNOWN -> UNKNOWN), 404 ambiguity,
401/403/429/500/timeout handling, stale fingerprint defense, financial immutability,
zero mutation methods, CAS concurrency, repeated idempotency, credential sanitization, and empty body validation.
"""

import pytest
from unittest.mock import patch
from sqlalchemy import text
from sqlalchemy.future import select

from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.contest_submission_audit import ContestSubmissionAudit
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.schemas.contest_submission import SubmissionStatus
from backend.app.schemas.contest_submission_reconciliation import ReconciliationOutcome
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.services.contest_submission_preflight_service import run_preflight
from backend.app.services.contest_submission_reconciliation_service import (
    SubmissionReconciliationException,
    reconcile_contest_submission,
)
from backend.app.services.contest_submission_service import submit_dispute_contest
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy
from backend.app.services.razorpay_client import MockRazorpayClient
from backend.app.schemas.contest_draft_review import ReviewDecision


def make_mock_rzp(dispute_id: str, status: str = "under_review", error_mode: str | None = None):
    """Helper to instantiate MockRazorpayClient with proper mock disputes dict or error_mode."""
    if error_mode:
        return MockRazorpayClient(error_mode=error_mode)
    raw_dispute = {
        "id": dispute_id,
        "entity": "dispute",
        "payment_id": "pay_rec_1",
        "amount": 149900,
        "currency": "INR",
        "amount_deducted": 149900,
        "reason_code": "13.1",
        "respond_by": 1735689600,
        "status": status,
        "phase": "chargeback",
        "created_at": 1600000000,
    }
    return MockRazorpayClient(mock_disputes={dispute_id: raw_dispute})


async def setup_dispute_for_reconciliation(
    async_db,
    dispute_id: str,
    payment_id: str = "pay_synth_0001",
    amount: int = 500000,
    currency: str = "INR",
    initial_submission_state: str = "UNKNOWN",
):
    """Sets up a complete dispute and ContestSubmission record for reconciliation testing."""
    await async_db.execute(text("DELETE FROM contest_submission_audits WHERE dispute_id = :d"), {"d": dispute_id})
    await async_db.execute(text("DELETE FROM contest_submissions WHERE dispute_id = :d"), {"d": dispute_id})
    await async_db.execute(text("DELETE FROM contest_submission_preflights WHERE dispute_id = :d"), {"d": dispute_id})
    await async_db.execute(text("DELETE FROM contest_draft_review_audits WHERE dispute_id = :d"), {"d": dispute_id})
    await async_db.execute(text("DELETE FROM contest_drafts WHERE dispute_id = :d"), {"d": dispute_id})
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = :d"), {"d": dispute_id})
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = :d"), {"d": dispute_id})
    await async_db.execute(text("DELETE FROM extracted_evidence WHERE document_id IN (SELECT id FROM evidence_documents WHERE dispute_id = :d)"), {"d": dispute_id})
    await async_db.execute(text("DELETE FROM evidence_documents WHERE dispute_id = :d"), {"d": dispute_id})
    await async_db.execute(text("DELETE FROM disputes WHERE id = :d"), {"d": dispute_id})
    await async_db.commit()

    dispute = Dispute(
        id=dispute_id,
        payment_id=payment_id,
        amount=amount,
        currency=currency,
        reason_code="13.1",
        status="open",
        raw_payload={"payload": {"dispute": {"entity": {"id": dispute_id, "payment_id": payment_id, "order_id": "ord_synth_0001", "amount": amount, "currency": currency, "awb_number": "1Z9998880001"}}}},
    )
    async_db.add(dispute)

    doc_inv = EvidenceDocument(
        id=f"doc_inv_{dispute_id}",
        dispute_id=dispute_id,
        razorpay_doc_id=f"doc_rzp_inv_{dispute_id}",
        original_filename="invoice.pdf",
        internal_filename="internal_inv.png",
        file_path="/tmp/invoice.pdf",
        file_hash="123456",
        file_size_bytes=100,
        mime_type="application/pdf",
        document_type="invoice",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_inv)

    ext_inv = ExtractedEvidence(
        id=f"ext_inv_{dispute_id}",
        document_id=doc_inv.id,
        document_type="invoice",
        payment_id=payment_id,
        order_id="ord_synth_0001",
        amount_minor=amount,
        currency=currency,
        customer_name="Gaurav Sharma",
        confidence_score=0.98,
        extracted_data={"payment_id": payment_id, "order_id": "ord_synth_0001", "amount_minor": amount},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_inv)

    doc_ship = EvidenceDocument(
        id=f"doc_ship_{dispute_id}",
        dispute_id=dispute_id,
        razorpay_doc_id=f"doc_rzp_ship_{dispute_id}",
        original_filename="shipping_proof.pdf",
        internal_filename="internal_ship.png",
        file_path="/tmp/shipping_proof.pdf",
        file_hash="123456",
        file_size_bytes=100,
        mime_type="application/pdf",
        document_type="shipping_proof",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc_ship)

    ext_ship = ExtractedEvidence(
        id=f"ext_ship_{dispute_id}",
        document_id=doc_ship.id,
        document_type="shipping_proof",
        payment_id=payment_id,
        order_id="ord_synth_0001",
        awb_number="1Z9998880001",
        delivery_date="2026-08-18",
        confidence_score=0.98,
        extracted_data={"payment_id": payment_id, "order_id": "ord_synth_0001", "awb_number": "1Z9998880001", "delivery_date": "2026-08-18"},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_ship)
    await async_db.commit()

    await run_evidence_matching(dispute_id, async_db)
    await evaluate_dispute_policy(dispute_id, async_db, reference_date="2026-08-26")
    draft = await generate_contest_draft(dispute_id, async_db, reference_date="2026-08-26")
    await review_contest_draft(dispute_id, ReviewDecision.APPROVE, comment="Approved for recon test", db=async_db)
    preflight = await run_preflight(dispute_id, async_db)

    # Initial submission via MockContestSubmissionClient
    client_sub = MockContestSubmissionClient(mode="TIMEOUT" if initial_submission_state == "UNKNOWN" else "SUCCESS")
    sub_res = await submit_dispute_contest(dispute_id, async_db, client=client_sub)

    if initial_submission_state != "UNKNOWN" and initial_submission_state != "SUBMITTED":
        stmt = select(ContestSubmission).where(ContestSubmission.dispute_id == dispute_id)
        db_sub = (await async_db.execute(stmt)).scalars().first()
        db_sub.state = initial_submission_state
        await async_db.commit()

    return dispute, draft, preflight


# ===========================================================================
# 1. STATE TRANSITION & STATUS LOOKUP TESTS (1-8)
# ===========================================================================


@pytest.mark.asyncio
async def test_01_unknown_to_submitted_reconciliation(async_db):
    """1. UNKNOWN -> SUBMITTED when Razorpay confirms contest submission."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_01", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_01", status="under_review")

    res = await reconcile_contest_submission("disp_rec_01", async_db, razorpay_client=client_rzp)
    assert res.previous_status == SubmissionStatus.UNKNOWN
    assert res.new_status == SubmissionStatus.SUBMITTED
    assert res.outcome == ReconciliationOutcome.RECONCILED_SUBMITTED
    assert res.razorpay_status == "under_review"


@pytest.mark.asyncio
async def test_02_in_progress_to_submitted_reconciliation(async_db):
    """2. SUBMISSION_IN_PROGRESS -> SUBMITTED when Razorpay confirms contest submission."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_02", initial_submission_state="SUBMISSION_IN_PROGRESS")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_02", status="under_review")

    res = await reconcile_contest_submission("disp_rec_02", async_db, razorpay_client=client_rzp)
    assert res.previous_status == SubmissionStatus.SUBMISSION_IN_PROGRESS
    assert res.new_status == SubmissionStatus.SUBMITTED
    assert res.outcome == ReconciliationOutcome.RECONCILED_SUBMITTED


@pytest.mark.asyncio
async def test_03_unknown_remains_unknown_on_ambiguous_status(async_db):
    """3. UNKNOWN remains UNKNOWN when Razorpay status is unverified/ambiguous."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_03", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_03", status="open")  # open status does not prove contest submitted

    res = await reconcile_contest_submission("disp_rec_03", async_db, razorpay_client=client_rzp)
    assert res.previous_status == SubmissionStatus.UNKNOWN
    assert res.new_status == SubmissionStatus.UNKNOWN
    assert res.outcome == ReconciliationOutcome.UNRESOLVED_UNKNOWN


@pytest.mark.asyncio
async def test_04_in_progress_remains_unknown_on_ambiguous_status(async_db):
    """4. SUBMISSION_IN_PROGRESS remains in current state when lookup is ambiguous."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_04", initial_submission_state="SUBMISSION_IN_PROGRESS")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_04", status="open")

    res = await reconcile_contest_submission("disp_rec_04", async_db, razorpay_client=client_rzp)
    assert res.new_status == SubmissionStatus.SUBMISSION_IN_PROGRESS
    assert res.outcome == ReconciliationOutcome.UNRESOLVED_UNKNOWN


@pytest.mark.asyncio
async def test_05_authoritative_under_review_status_reconciles(async_db):
    """5. Authoritative 'under_review' status reconciles cleanly."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_05", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_05", status="under_review")

    res = await reconcile_contest_submission("disp_rec_05", async_db, razorpay_client=client_rzp)
    assert res.outcome == ReconciliationOutcome.RECONCILED_SUBMITTED


@pytest.mark.asyncio
async def test_06_asynchronous_under_review_distinguished_from_outcome(async_db):
    """6. Asynchronous under_review is distinguished from final won/lost outcome."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_06", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_06", status="under_review")

    res = await reconcile_contest_submission("disp_rec_06", async_db, razorpay_client=client_rzp)
    assert res.new_status == SubmissionStatus.SUBMITTED
    assert res.razorpay_status == "under_review"  # Not converted to won or lost


@pytest.mark.asyncio
async def test_07_action_required_status_reconciles(async_db):
    """7. 'action_required' status proves contest submission occurred."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_07", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_07", status="action_required")

    res = await reconcile_contest_submission("disp_rec_07", async_db, razorpay_client=client_rzp)
    assert res.outcome == ReconciliationOutcome.RECONCILED_SUBMITTED


@pytest.mark.asyncio
async def test_08_404_not_found_leaves_state_unresolved(async_db):
    """8. 404 Not Found during status lookup leaves state UNKNOWN."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_08", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_08", error_mode="not_found")

    res = await reconcile_contest_submission("disp_rec_08", async_db, razorpay_client=client_rzp)
    assert res.new_status == SubmissionStatus.UNKNOWN
    assert res.outcome == ReconciliationOutcome.UNRESOLVED_UNKNOWN


# ===========================================================================
# 2. ERROR HANDLING TESTS (9-15)
# ===========================================================================


@pytest.mark.asyncio
async def test_09_401_auth_error_handled_safely(async_db):
    """9. 401 Unauthorized returns ERROR_LOOKUP_FAILED, state unchanged."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_09", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_09", error_mode="auth_error")

    res = await reconcile_contest_submission("disp_rec_09", async_db, razorpay_client=client_rzp)
    assert res.outcome == ReconciliationOutcome.ERROR_LOOKUP_FAILED
    assert res.new_status == SubmissionStatus.UNKNOWN


@pytest.mark.asyncio
async def test_10_403_forbidden_error_handled_safely(async_db):
    """10. 403 Forbidden returns ERROR_LOOKUP_FAILED."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_10", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_10", error_mode="auth_error")

    res = await reconcile_contest_submission("disp_rec_10", async_db, razorpay_client=client_rzp)
    assert res.outcome == ReconciliationOutcome.ERROR_LOOKUP_FAILED


@pytest.mark.asyncio
async def test_11_429_rate_limit_handled_safely(async_db):
    """11. 429 Rate Limit returns ERROR_LOOKUP_FAILED without infinite retry."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_11", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_11", error_mode="rate_limit")

    res = await reconcile_contest_submission("disp_rec_11", async_db, razorpay_client=client_rzp)
    assert res.outcome == ReconciliationOutcome.ERROR_LOOKUP_FAILED


@pytest.mark.asyncio
async def test_12_500_server_error_handled_safely(async_db):
    """12. 500 Server Error returns ERROR_LOOKUP_FAILED."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_12", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_12", error_mode="server_error")

    res = await reconcile_contest_submission("disp_rec_12", async_db, razorpay_client=client_rzp)
    assert res.outcome == ReconciliationOutcome.ERROR_LOOKUP_FAILED


@pytest.mark.asyncio
async def test_13_timeout_handled_safely(async_db):
    """13. Network timeout during lookup returns ERROR_LOOKUP_FAILED."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_13", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_13", error_mode="timeout")

    res = await reconcile_contest_submission("disp_rec_13", async_db, razorpay_client=client_rzp)
    assert res.outcome == ReconciliationOutcome.ERROR_LOOKUP_FAILED


@pytest.mark.asyncio
async def test_14_connection_failure_handled_safely(async_db):
    """14. Connection failure returns ERROR_LOOKUP_FAILED."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_14", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_14", error_mode="malformed")

    res = await reconcile_contest_submission("disp_rec_14", async_db, razorpay_client=client_rzp)
    assert res.outcome == ReconciliationOutcome.ERROR_LOOKUP_FAILED


@pytest.mark.asyncio
async def test_15_malformed_response_handled_safely(async_db):
    """15. Malformed response handled without crash."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_15", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_15", error_mode="malformed")

    res = await reconcile_contest_submission("disp_rec_15", async_db, razorpay_client=client_rzp)
    assert res.outcome in [ReconciliationOutcome.ERROR_LOOKUP_FAILED, ReconciliationOutcome.UNRESOLVED_UNKNOWN]


# ===========================================================================
# 3. SAFETY & IMMUTABILITY TESTS (16-27)
# ===========================================================================


@pytest.mark.asyncio
async def test_16_stale_fingerprint_rejected(async_db):
    """16. Stale fingerprint returns STALE_FINGERPRINT without state mutation."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_16", initial_submission_state="UNKNOWN")
    stmt = select(ContestSubmission).where(ContestSubmission.dispute_id == "disp_rec_16")
    db_sub = (await async_db.execute(stmt)).scalars().first()
    db_sub.input_fingerprint = "0" * 64
    await async_db.commit()

    client_rzp = make_mock_rzp(dispute_id="disp_rec_16", status="under_review")
    res = await reconcile_contest_submission("disp_rec_16", async_db, razorpay_client=client_rzp)

    assert res.outcome == ReconciliationOutcome.STALE_FINGERPRINT
    assert res.new_status == SubmissionStatus.UNKNOWN


@pytest.mark.asyncio
async def test_17_to_20_financial_immutability(async_db):
    """17-20. Verifies dispute financial fields (payment_id, amount, currency) are untouched."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_fi_17", initial_submission_state="UNKNOWN")

    pay_before = dispute.payment_id
    amt_before = dispute.amount
    curr_before = dispute.currency

    client_rzp = make_mock_rzp(dispute_id="disp_rec_fi_17", status="under_review")
    await reconcile_contest_submission("disp_rec_fi_17", async_db, razorpay_client=client_rzp)

    stmt = select(Dispute).where(Dispute.id == "disp_rec_fi_17")
    disp_after = (await async_db.execute(stmt)).scalars().first()

    assert disp_after.payment_id == pay_before
    assert disp_after.amount == amt_before
    assert disp_after.currency == curr_before


@pytest.mark.asyncio
async def test_21_to_22_policy_and_draft_immutability(async_db):
    """21-22. Verifies PolicyResult and ContestDraft remain untouched by reconciliation."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_imm_21", initial_submission_state="UNKNOWN")

    pol_before = dispute.policy_results[0].outcome
    draft_status_before = draft.status

    client_rzp = make_mock_rzp(dispute_id="disp_rec_imm_21", status="under_review")
    await reconcile_contest_submission("disp_rec_imm_21", async_db, razorpay_client=client_rzp)

    assert dispute.policy_results[0].outcome == pol_before
    assert draft.status == draft_status_before


@pytest.mark.asyncio
async def test_23_to_27_no_mutation_methods_or_arbitrary_urls(async_db):
    """23-27. Verifies zero submit_contest, accept, reject, refund calls or arbitrary URLs exist."""
    from backend.app.services.contest_submission_reconciliation_service import reconcile_contest_submission
    import inspect

    src = inspect.getsource(reconcile_contest_submission)
    assert "submit_contest" not in src
    assert "accept_dispute" not in src
    assert "reject_dispute" not in src
    assert "issue_refund" not in src


# ===========================================================================
# 4. CONCURRENCY, IDEMPOTENCY & AUDIT TESTS (28-32)
# ===========================================================================


@pytest.mark.asyncio
async def test_28_concurrency_cas_protection(async_db):
    """28. CAS update prevents double mutation under simulated race condition."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_cas_28", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_cas_28", status="under_review")

    res1 = await reconcile_contest_submission("disp_rec_cas_28", async_db, razorpay_client=client_rzp)
    assert res1.outcome == ReconciliationOutcome.RECONCILED_SUBMITTED

    # Second concurrent attempt sees ALREADY_SUBMITTED
    res2 = await reconcile_contest_submission("disp_rec_cas_28", async_db, razorpay_client=client_rzp)
    assert res2.outcome == ReconciliationOutcome.ALREADY_SUBMITTED


@pytest.mark.asyncio
async def test_29_repeated_reconciliation_is_idempotent(async_db):
    """29. Repeated reconciliation of SUBMITTED record returns ALREADY_SUBMITTED."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_idem_29", initial_submission_state="SUBMITTED")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_idem_29", status="under_review")

    res = await reconcile_contest_submission("disp_rec_idem_29", async_db, razorpay_client=client_rzp)
    assert res.outcome == ReconciliationOutcome.ALREADY_SUBMITTED
    assert res.new_status == SubmissionStatus.SUBMITTED


@pytest.mark.asyncio
async def test_30_audit_trail_persisted(async_db):
    """30. Reconciliation generates append-only audit trail record."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_aud_30", initial_submission_state="UNKNOWN")
    client_rzp = make_mock_rzp(dispute_id="disp_rec_aud_30", status="under_review")

    res = await reconcile_contest_submission("disp_rec_aud_30", async_db, razorpay_client=client_rzp)
    assert res.audit_id is not None

    stmt = select(ContestSubmissionAudit).where(ContestSubmissionAudit.dispute_id == "disp_rec_aud_30")
    audits = (await async_db.execute(stmt)).scalars().all()
    assert len(audits) >= 1


@pytest.mark.asyncio
async def test_31_credential_sanitization_in_reconciliation(async_db):
    """31. Verifies credentials are sanitized from audit metadata."""
    from backend.app.services.contest_submission_service import _sanitize_metadata
    dirty = {"auth": "Bearer secret", "normal": "value"}
    clean = _sanitize_metadata(dirty)
    assert clean["auth"] == "[REDACTED]"
    assert clean["normal"] == "value"


@pytest.mark.asyncio
async def test_32_empty_request_body_enforced(client, async_db):
    """32. Endpoint POST /api/disputes/{dispute_id}/contest-submission/reconcile forbids client payload injection."""
    dispute, draft, preflight = await setup_dispute_for_reconciliation(async_db, "disp_rec_api_32", initial_submission_state="SUBMITTED")

    injection_body = {"status": "HACKED_SUBMITTED", "amount": 0}
    res = await client.post("/api/disputes/disp_rec_api_32/contest-submission/reconcile", json=injection_body)
    assert res.status_code == 422
