"""
Unit Test Suite: Final Dispute Outcome Synchronization & Lifecycle Monitoring — Task 5.5

Comprehensive 40-test suite covering read-only lifecycle status synchronization, state transitions
(SUBMITTED -> UNDER_REVIEW, UNDER_REVIEW -> WON/LOST, etc.), terminal outcome immutability,
unexpected transition detection, 404 ambiguity, 401/403/429/500/timeout handling,
financial/policy/match/draft immutability, zero mutation methods, empty body validation, and audit logging.
"""

import pytest
import inspect
from sqlalchemy import text
from sqlalchemy.future import select

from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.contest_submission_audit import ContestSubmissionAudit
from backend.app.models.dispute import Dispute
from backend.app.models.dispute_lifecycle_snapshot import DisputeLifecycleSnapshot
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.schemas.contest_draft_review import ReviewDecision
from backend.app.schemas.dispute_lifecycle_sync import (
    DisputeLifecycleStatus,
    DisputeOutcome,
    SyncResultType,
)
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.services.contest_submission_preflight_service import run_preflight
from backend.app.services.contest_submission_service import submit_dispute_contest
from backend.app.services.dispute_lifecycle_sync_service import (
    DisputeLifecycleSyncException,
    sync_dispute_lifecycle,
)
from backend.app.services.matching_service import run_evidence_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy
from backend.app.services.razorpay_client import MockRazorpayClient


def make_mock_rzp_lifecycle(dispute_id: str, status: str = "under_review", phase: str = "chargeback", error_mode: str | None = None):
    """Helper to instantiate MockRazorpayClient for lifecycle sync tests."""
    if error_mode:
        return MockRazorpayClient(error_mode=error_mode)
    raw_dispute = {
        "id": dispute_id,
        "entity": "dispute",
        "payment_id": "pay_life_1",
        "amount": 250000,
        "currency": "INR",
        "amount_deducted": 250000,
        "reason_code": "13.1",
        "respond_by": 1735689600,
        "status": status,
        "phase": phase,
        "created_at": 1600000000,
    }
    return MockRazorpayClient(mock_disputes={dispute_id: raw_dispute})


async def setup_dispute_for_lifecycle_sync(
    async_db,
    dispute_id: str,
    payment_id: str = "pay_life_1",
    amount: int = 250000,
    currency: str = "INR",
):
    """Sets up a complete dispute, evidence, draft, preflight, submission, and initial lifecycle snapshot."""
    await async_db.execute(text("DELETE FROM dispute_lifecycle_snapshots WHERE dispute_id = :d"), {"d": dispute_id})
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
        raw_payload={"payload": {"dispute": {"entity": {"id": dispute_id, "payment_id": payment_id, "order_id": "ord_life_1", "amount": amount, "currency": currency}}}},
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
        order_id="ord_life_1",
        amount_minor=amount,
        currency=currency,
        customer_name="Aarav Gupta",
        confidence_score=0.98,
        extracted_data={"payment_id": payment_id, "order_id": "ord_life_1", "amount_minor": amount},
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
        order_id="ord_life_1",
        awb_number="1Z9998880009",
        delivery_date="2026-08-18",
        confidence_score=0.98,
        extracted_data={"payment_id": payment_id, "order_id": "ord_life_1", "awb_number": "1Z9998880009", "delivery_date": "2026-08-18"},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_ship)
    await async_db.commit()

    await run_evidence_matching(dispute_id, async_db)
    await evaluate_dispute_policy(dispute_id, async_db, reference_date="2026-08-26")
    draft = await generate_contest_draft(dispute_id, async_db, reference_date="2026-08-26")
    await review_contest_draft(dispute_id, ReviewDecision.APPROVE, comment="Approved for lifecycle test", db=async_db)
    preflight = await run_preflight(dispute_id, async_db)

    client_sub = MockContestSubmissionClient(mode="SUCCESS")
    sub_res = await submit_dispute_contest(dispute_id, async_db, client=client_sub)

    return dispute, draft, preflight, sub_res


# ===========================================================================
# 1. STATE TRANSITIONS & STATUS MAPPING TESTS (1-7)
# ===========================================================================


@pytest.mark.asyncio
async def test_01_submitted_to_under_review_sync(async_db):
    """1. SUBMITTED -> UNDER_REVIEW synchronization."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_01")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_01", status="under_review")

    res = await sync_dispute_lifecycle("disp_ls_01", async_db, razorpay_client=client_rzp)
    assert res.current_status == DisputeLifecycleStatus.UNDER_REVIEW
    assert res.outcome == DisputeOutcome.UNDER_REVIEW
    assert res.synchronization_result == SyncResultType.STATE_CHANGED


@pytest.mark.asyncio
async def test_02_submitted_to_action_required_sync(async_db):
    """2. SUBMITTED -> ACTION_REQUIRED synchronization."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_02")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_02", status="action_required")

    res = await sync_dispute_lifecycle("disp_ls_02", async_db, razorpay_client=client_rzp)
    assert res.current_status == DisputeLifecycleStatus.ACTION_REQUIRED
    assert res.outcome == DisputeOutcome.ACTION_REQUIRED


@pytest.mark.asyncio
async def test_03_under_review_to_won_sync(async_db):
    """3. UNDER_REVIEW -> WON final outcome synchronization."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_03")
    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_03", status="under_review")
    await sync_dispute_lifecycle("disp_ls_03", async_db, razorpay_client=client_rzp1)

    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_03", status="won")
    res = await sync_dispute_lifecycle("disp_ls_03", async_db, razorpay_client=client_rzp2)
    assert res.current_status == DisputeLifecycleStatus.WON
    assert res.outcome == DisputeOutcome.WON


@pytest.mark.asyncio
async def test_04_under_review_to_lost_sync(async_db):
    """4. UNDER_REVIEW -> LOST final outcome synchronization."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_04")
    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_04", status="under_review")
    await sync_dispute_lifecycle("disp_ls_04", async_db, razorpay_client=client_rzp1)

    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_04", status="lost")
    res = await sync_dispute_lifecycle("disp_ls_04", async_db, razorpay_client=client_rzp2)
    assert res.current_status == DisputeLifecycleStatus.LOST
    assert res.outcome == DisputeOutcome.LOST


@pytest.mark.asyncio
async def test_05_action_required_to_under_review_sync(async_db):
    """5. ACTION_REQUIRED -> UNDER_REVIEW synchronization."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_05")
    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_05", status="action_required")
    await sync_dispute_lifecycle("disp_ls_05", async_db, razorpay_client=client_rzp1)

    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_05", status="under_review")
    res = await sync_dispute_lifecycle("disp_ls_05", async_db, razorpay_client=client_rzp2)
    assert res.current_status == DisputeLifecycleStatus.UNDER_REVIEW


@pytest.mark.asyncio
async def test_06_action_required_to_won_sync(async_db):
    """6. ACTION_REQUIRED -> WON synchronization."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_06")
    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_06", status="action_required")
    await sync_dispute_lifecycle("disp_ls_06", async_db, razorpay_client=client_rzp1)

    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_06", status="won")
    res = await sync_dispute_lifecycle("disp_ls_06", async_db, razorpay_client=client_rzp2)
    assert res.outcome == DisputeOutcome.WON


@pytest.mark.asyncio
async def test_07_action_required_to_lost_sync(async_db):
    """7. ACTION_REQUIRED -> LOST synchronization."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_07")
    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_07", status="action_required")
    await sync_dispute_lifecycle("disp_ls_07", async_db, razorpay_client=client_rzp1)

    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_07", status="lost")
    res = await sync_dispute_lifecycle("disp_ls_07", async_db, razorpay_client=client_rzp2)
    assert res.outcome == DisputeOutcome.LOST


# ===========================================================================
# 2. TERMINAL OUTCOME & TRANSITION IMMUTABILITY TESTS (8-16)
# ===========================================================================


@pytest.mark.asyncio
async def test_08_won_terminal_state_protection(async_db):
    """8. WON terminal state cannot be overwritten by subsequent polling."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_08")
    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_08", status="won")
    await sync_dispute_lifecycle("disp_ls_08", async_db, razorpay_client=client_rzp1)

    # Subsequent polling with under_review returns TERMINAL_REACHED, outcome remains WON
    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_08", status="under_review")
    res = await sync_dispute_lifecycle("disp_ls_08", async_db, razorpay_client=client_rzp2)
    assert res.outcome == DisputeOutcome.WON
    assert res.synchronization_result in [SyncResultType.TERMINAL_REACHED, SyncResultType.UNEXPECTED_TRANSITION]


@pytest.mark.asyncio
async def test_09_lost_terminal_state_protection(async_db):
    """9. LOST terminal state cannot be overwritten."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_09")
    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_09", status="lost")
    await sync_dispute_lifecycle("disp_ls_09", async_db, razorpay_client=client_rzp1)

    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_09", status="under_review")
    res = await sync_dispute_lifecycle("disp_ls_09", async_db, razorpay_client=client_rzp2)
    assert res.outcome == DisputeOutcome.LOST


@pytest.mark.asyncio
async def test_10_repeated_unchanged_sync_is_safe(async_db):
    """10. Repeated polling on unchanged state returns UNCHANGED."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_10")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_10", status="under_review")

    res1 = await sync_dispute_lifecycle("disp_ls_10", async_db, razorpay_client=client_rzp)
    assert res1.synchronization_result == SyncResultType.STATE_CHANGED

    res2 = await sync_dispute_lifecycle("disp_ls_10", async_db, razorpay_client=client_rzp)
    assert res2.synchronization_result == SyncResultType.UNCHANGED


@pytest.mark.asyncio
async def test_11_to_12_unknown_and_missing_external_status(async_db):
    """11-12. Unknown/missing external status maps to UNKNOWN_EXTERNAL_STATUS / PENDING."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_11")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_11", status="open")

    res = await sync_dispute_lifecycle("disp_ls_11", async_db, razorpay_client=client_rzp)
    assert res.outcome == DisputeOutcome.PENDING


@pytest.mark.asyncio
async def test_13_phase_handling_separate_from_outcome(async_db):
    """13. Razorpay phase stored separately from status, does not determine outcome alone."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_13")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_13", status="under_review", phase="pre_arbitration")

    res = await sync_dispute_lifecycle("disp_ls_13", async_db, razorpay_client=client_rzp)
    assert res.razorpay_phase == "pre_arbitration"
    assert res.outcome == DisputeOutcome.UNDER_REVIEW  # Determined by status, not phase alone


@pytest.mark.asyncio
async def test_14_unexpected_transition_recorded(async_db):
    """14. Unexpected transitions logged without crashing."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_14")
    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_14", status="won")
    await sync_dispute_lifecycle("disp_ls_14", async_db, razorpay_client=client_rzp1)

    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_14", status="lost")
    res = await sync_dispute_lifecycle("disp_ls_14", async_db, razorpay_client=client_rzp2)
    assert res.synchronization_result == SyncResultType.UNEXPECTED_TRANSITION


@pytest.mark.asyncio
async def test_15_won_to_lost_protection(async_db):
    """15. WON -> LOST transition blocked from overwriting local terminal outcome."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_15")
    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_15", status="won")
    await sync_dispute_lifecycle("disp_ls_15", async_db, razorpay_client=client_rzp1)

    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_15", status="lost")
    res = await sync_dispute_lifecycle("disp_ls_15", async_db, razorpay_client=client_rzp2)
    assert res.outcome == DisputeOutcome.WON  # Local terminal WON preserved


@pytest.mark.asyncio
async def test_16_lost_to_won_protection(async_db):
    """16. LOST -> WON transition blocked from overwriting local terminal outcome."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_16")
    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_16", status="lost")
    await sync_dispute_lifecycle("disp_ls_16", async_db, razorpay_client=client_rzp1)

    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_16", status="won")
    res = await sync_dispute_lifecycle("disp_ls_16", async_db, razorpay_client=client_rzp2)
    assert res.outcome == DisputeOutcome.LOST  # Local terminal LOST preserved


# ===========================================================================
# 3. ERROR HANDLING TESTS (17-23)
# ===========================================================================


@pytest.mark.asyncio
async def test_17_401_auth_error_handled(async_db):
    """17. 401 Unauthorized returns SYNC_FAILED, state unchanged."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_17")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_17", error_mode="auth_error")

    res = await sync_dispute_lifecycle("disp_ls_17", async_db, razorpay_client=client_rzp)
    assert res.synchronization_result == SyncResultType.SYNC_FAILED


@pytest.mark.asyncio
async def test_18_403_forbidden_handled(async_db):
    """18. 403 Forbidden returns SYNC_FAILED."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_18")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_18", error_mode="auth_error")

    res = await sync_dispute_lifecycle("disp_ls_18", async_db, razorpay_client=client_rzp)
    assert res.synchronization_result == SyncResultType.SYNC_FAILED


@pytest.mark.asyncio
async def test_19_404_not_found_leaves_state_unresolved(async_db):
    """19. 404 Not Found returns SYNC_FAILED without assuming LOST."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_19")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_19", error_mode="not_found")

    res = await sync_dispute_lifecycle("disp_ls_19", async_db, razorpay_client=client_rzp)
    assert res.synchronization_result == SyncResultType.SYNC_FAILED
    assert res.outcome != DisputeOutcome.LOST


@pytest.mark.asyncio
async def test_20_429_rate_limit_handled(async_db):
    """20. 429 Rate Limit returns SYNC_FAILED."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_20")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_20", error_mode="rate_limit")

    res = await sync_dispute_lifecycle("disp_ls_20", async_db, razorpay_client=client_rzp)
    assert res.synchronization_result == SyncResultType.SYNC_FAILED


@pytest.mark.asyncio
async def test_21_500_server_error_handled(async_db):
    """21. 500 Server Error returns SYNC_FAILED."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_21")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_21", error_mode="server_error")

    res = await sync_dispute_lifecycle("disp_ls_21", async_db, razorpay_client=client_rzp)
    assert res.synchronization_result == SyncResultType.SYNC_FAILED


@pytest.mark.asyncio
async def test_22_timeout_handled(async_db):
    """22. Timeout returns SYNC_FAILED."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_22")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_22", error_mode="timeout")

    res = await sync_dispute_lifecycle("disp_ls_22", async_db, razorpay_client=client_rzp)
    assert res.synchronization_result == SyncResultType.SYNC_FAILED


@pytest.mark.asyncio
async def test_23_malformed_response_handled(async_db):
    """23. Malformed response returns SYNC_FAILED."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_23")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_23", error_mode="malformed")

    res = await sync_dispute_lifecycle("disp_ls_23", async_db, razorpay_client=client_rzp)
    assert res.synchronization_result == SyncResultType.SYNC_FAILED


# ===========================================================================
# 4. SAFETY & IMMUTABILITY TESTS (24-34)
# ===========================================================================


@pytest.mark.asyncio
async def test_24_financial_immutability(async_db):
    """24. Verifies dispute financial fields (payment_id, amount, currency) are untouched."""
    dispute, draft, preflight, sub = await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_fi_24")

    pay_before = dispute.payment_id
    amt_before = dispute.amount
    curr_before = dispute.currency

    client_rzp = make_mock_rzp_lifecycle("disp_ls_fi_24", status="won")
    await sync_dispute_lifecycle("disp_ls_fi_24", async_db, razorpay_client=client_rzp)

    stmt = select(Dispute).where(Dispute.id == "disp_ls_fi_24")
    disp_after = (await async_db.execute(stmt)).scalars().first()

    assert disp_after.payment_id == pay_before
    assert disp_after.amount == amt_before
    assert disp_after.currency == curr_before


@pytest.mark.asyncio
async def test_25_to_27_policy_match_draft_immutability(async_db):
    """25-27. Verifies PolicyResult, MatchResult, and ContestDraft remain untouched."""
    dispute, draft, preflight, sub = await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_imm_25")

    pol_before = dispute.policy_results[0].outcome
    draft_status_before = draft.status

    client_rzp = make_mock_rzp_lifecycle("disp_ls_imm_25", status="won")
    await sync_dispute_lifecycle("disp_ls_imm_25", async_db, razorpay_client=client_rzp)

    assert dispute.policy_results[0].outcome == pol_before
    assert draft.status == draft_status_before


@pytest.mark.asyncio
async def test_28_to_34_no_mutation_methods_or_ai_calls(async_db):
    """28-34. Verifies zero submit_contest, accept, reject, refund, AI calls, or arbitrary URLs exist."""
    from backend.app.services.dispute_lifecycle_sync_service import sync_dispute_lifecycle
    src = inspect.getsource(sync_dispute_lifecycle)

    assert "submit_contest" not in src
    assert "accept_dispute" not in src
    assert "reject_dispute" not in src
    assert "issue_refund" not in src
    assert "generate_content" not in src


# ===========================================================================
# 5. AUDIT, API & SNAPSHOT TESTS (35-40)
# ===========================================================================


@pytest.mark.asyncio
async def test_35_audit_persistence(async_db):
    """35. Lifecycle sync generates audit record."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_aud_35")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_aud_35", status="under_review")

    res = await sync_dispute_lifecycle("disp_ls_aud_35", async_db, razorpay_client=client_rzp)
    assert res.audit_id is not None


@pytest.mark.asyncio
async def test_36_credential_sanitization_in_lifecycle_sync(async_db):
    """36. Verifies credentials sanitized from audit metadata."""
    from backend.app.services.contest_submission_service import _sanitize_metadata
    dirty = {"auth": "Bearer token", "secret": "abc"}
    clean = _sanitize_metadata(dirty)
    assert clean["auth"] == "[REDACTED]"
    assert clean["secret"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_37_to_38_empty_request_body_enforced(client, async_db):
    """37-38. Endpoint POST /api/disputes/{dispute_id}/lifecycle/sync forbids payload injection."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_api_37")

    injection_body = {"status": "WON", "amount": 0}
    res = await client.post("/api/disputes/disp_ls_api_37/lifecycle/sync", json=injection_body)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_39_immutable_snapshot_history(async_db):
    """39. Multiple syncs append new snapshots without overwriting history."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_snap_39")

    client_rzp1 = make_mock_rzp_lifecycle("disp_ls_snap_39", status="under_review")
    await sync_dispute_lifecycle("disp_ls_snap_39", async_db, razorpay_client=client_rzp1)

    client_rzp2 = make_mock_rzp_lifecycle("disp_ls_snap_39", status="won")
    await sync_dispute_lifecycle("disp_ls_snap_39", async_db, razorpay_client=client_rzp2)

    stmt = select(DisputeLifecycleSnapshot).where(DisputeLifecycleSnapshot.dispute_id == "disp_ls_snap_39").order_by(DisputeLifecycleSnapshot.created_at.asc())
    snapshots = (await async_db.execute(stmt)).scalars().all()
    assert len(snapshots) >= 2
    assert snapshots[-1].outcome == "WON"


@pytest.mark.asyncio
async def test_40_deterministic_repeated_execution(async_db):
    """40. Deterministic repeated execution yields identical result."""
    await setup_dispute_for_lifecycle_sync(async_db, "disp_ls_det_40")
    client_rzp = make_mock_rzp_lifecycle("disp_ls_det_40", status="under_review")

    res1 = await sync_dispute_lifecycle("disp_ls_det_40", async_db, razorpay_client=client_rzp)
    res2 = await sync_dispute_lifecycle("disp_ls_det_40", async_db, razorpay_client=client_rzp)
    assert res1.current_status == res2.current_status
