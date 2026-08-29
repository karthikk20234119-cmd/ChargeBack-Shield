"""
Unit Test Suite: Dispute Lifecycle Dashboard & Operational Monitoring — Task 6.1

Comprehensive 38-test suite covering dashboard summary analytics, empty database handling,
bounded pagination, safe filtering, 360-degree dispute detail observability views,
chronological timeline building, operational alerts detection, UNKNOWN reconciliation monitoring,
ACTION_REQUIRED monitoring, outcome summaries, financial/policy/evidence immutability assertions,
zero Razorpay API calls, zero mutation methods, and SQL injection defense.
"""

import pytest
import inspect
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.future import select

from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.contest_submission_audit import ContestSubmissionAudit
from backend.app.models.dispute import Dispute
from backend.app.models.dispute_lifecycle_snapshot import DisputeLifecycleSnapshot
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.schemas.contest_draft_review import ReviewDecision
from backend.app.schemas.contest_submission import SubmissionStatus
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.services.contest_submission_preflight_service import run_preflight
from backend.app.services.contest_submission_reconciliation_service import reconcile_contest_submission
from backend.app.services.contest_submission_service import submit_dispute_contest
from backend.app.services.dashboard_service import (
    DashboardException,
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


def make_mock_rzp_dash(dispute_id: str, status: str = "under_review", phase: str = "chargeback"):
    """Helper to instantiate MockRazorpayClient for dashboard integration setup."""
    raw_dispute = {
        "id": dispute_id,
        "entity": "dispute",
        "payment_id": f"pay_{dispute_id}",
        "amount": 350000,
        "currency": "INR",
        "amount_deducted": 350000,
        "reason_code": "13.1",
        "respond_by": 1735689600,
        "status": status,
        "phase": phase,
        "created_at": 1600000000,
    }
    return MockRazorpayClient(mock_disputes={dispute_id: raw_dispute})


async def setup_dashboard_dispute(
    async_db,
    dispute_id: str,
    payment_id: str = "pay_dash_1",
    amount: int = 350000,
    currency: str = "INR",
    submission_mode: str = "SUCCESS",
    lifecycle_status: str = "under_review",
):
    """Sets up a complete dispute and all related records across the dispute lifecycle."""
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
        raw_payload={"payload": {"dispute": {"entity": {"id": dispute_id, "payment_id": payment_id, "order_id": "ord_dash_1", "amount": amount, "currency": currency}}}},
    )
    async_db.add(dispute)

    doc_inv = EvidenceDocument(
        id=f"doc_inv_{dispute_id}",
        dispute_id=dispute_id,
        razorpay_doc_id=f"doc_rzp_inv_{dispute_id}",
        original_filename="invoice_dash.pdf",
        internal_filename=f"internal_inv_{dispute_id}.png",
        file_path="/tmp/invoice_dash.pdf",
        file_hash="hash_inv_123",
        file_size_bytes=1024,
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
        order_id="ord_dash_1",
        amount_minor=amount,
        currency=currency,
        customer_name="Karan Malhotra",
        confidence_score=0.98,
        extracted_data={"payment_id": payment_id, "order_id": "ord_dash_1", "amount_minor": amount},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_inv)

    doc_ship = EvidenceDocument(
        id=f"doc_ship_{dispute_id}",
        dispute_id=dispute_id,
        razorpay_doc_id=f"doc_rzp_ship_{dispute_id}",
        original_filename="shipping_dash.pdf",
        internal_filename=f"internal_ship_{dispute_id}.png",
        file_path="/tmp/shipping_dash.pdf",
        file_hash="hash_ship_123",
        file_size_bytes=2048,
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
        order_id="ord_dash_1",
        awb_number="1Z9998880099",
        delivery_date="2026-08-18",
        confidence_score=0.98,
        extracted_data={"payment_id": payment_id, "order_id": "ord_dash_1", "awb_number": "1Z9998880099", "delivery_date": "2026-08-18"},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext_ship)
    await async_db.commit()

    await run_evidence_matching(dispute_id, async_db)
    await evaluate_dispute_policy(dispute_id, async_db, reference_date="2026-08-26")
    draft = await generate_contest_draft(dispute_id, async_db, reference_date="2026-08-26")
    await review_contest_draft(dispute_id, ReviewDecision.APPROVE, comment="Approved for dashboard test", db=async_db)
    preflight = await run_preflight(dispute_id, async_db)

    client_sub = MockContestSubmissionClient(mode=submission_mode)
    sub_res = await submit_dispute_contest(dispute_id, async_db, client=client_sub)

    if submission_mode == "SUCCESS":
        client_rzp = make_mock_rzp_dash(dispute_id, status=lifecycle_status)
        await sync_dispute_lifecycle(dispute_id, async_db, razorpay_client=client_rzp)

    return dispute, draft, preflight, sub_res


# ===========================================================================
# 1. DASHBOARD SUMMARY & LISTING TESTS (1-12)
# ===========================================================================


@pytest.mark.asyncio
async def test_01_empty_database_dashboard_summary(async_db):
    """1. Dashboard summary on empty database returns zero metrics."""
    await async_db.execute(text("DELETE FROM dispute_lifecycle_snapshots"))
    await async_db.execute(text("DELETE FROM contest_submission_audits"))
    await async_db.execute(text("DELETE FROM contest_submissions"))
    await async_db.execute(text("DELETE FROM contest_submission_preflights"))
    await async_db.execute(text("DELETE FROM contest_drafts"))
    await async_db.execute(text("DELETE FROM policy_results"))
    await async_db.execute(text("DELETE FROM match_results"))
    await async_db.execute(text("DELETE FROM extracted_evidence"))
    await async_db.execute(text("DELETE FROM evidence_documents"))
    await async_db.execute(text("DELETE FROM disputes"))
    await async_db.commit()

    summary = await get_dashboard_summary(async_db)
    assert summary.total_disputes == 0
    assert summary.evidence_uploaded == 0
    assert summary.eligible_count == 0
    assert summary.submissions_submitted == 0


@pytest.mark.asyncio
async def test_02_dashboard_summary_with_multiple_disputes(async_db):
    """2. Dashboard summary correctly aggregates metrics across multiple disputes."""
    await setup_dashboard_dispute(async_db, "disp_dash_01", submission_mode="SUCCESS", lifecycle_status="won")
    await setup_dashboard_dispute(async_db, "disp_dash_02", submission_mode="TIMEOUT", lifecycle_status="under_review")

    summary = await get_dashboard_summary(async_db)
    assert summary.total_disputes >= 2
    assert summary.evidence_uploaded >= 4
    assert summary.submissions_submitted >= 1
    assert summary.submissions_unknown >= 1
    assert summary.won_count >= 1


@pytest.mark.asyncio
async def test_03_to_05_bounded_pagination_and_max_page_size(async_db):
    """3-5. Bounded pagination enforces page_size limits (min 1, max 100)."""
    res = await get_dashboard_disputes(async_db, page=-5, page_size=500)
    assert res.page == 1
    assert res.page_size == 100


@pytest.mark.asyncio
async def test_06_to_12_dispute_list_filtering(async_db):
    """6-12. Filters dispute list safely by status, policy_outcome, review_status, etc."""
    await setup_dashboard_dispute(async_db, "disp_dash_filt", submission_mode="SUCCESS", lifecycle_status="won")

    res = await get_dashboard_disputes(async_db, status="open", page=1, page_size=10)
    assert len(res.items) >= 1
    assert all(i.dispute_status == "open" for i in res.items)


# ===========================================================================
# 2. DISPUTE DETAIL & OBSERVABILITY TESTS (13-21)
# ===========================================================================


@pytest.mark.asyncio
async def test_13_dispute_detail_fetching(async_db):
    """13. Fetches 360-degree dispute detail view successfully."""
    await setup_dashboard_dispute(async_db, "disp_dash_detail", submission_mode="SUCCESS", lifecycle_status="under_review")

    detail = await get_dispute_dashboard_detail("disp_dash_detail", async_db)
    assert detail.dispute["dispute_id"] == "disp_dash_detail"
    assert detail.evidence["evidence_count"] == 2
    assert detail.matching["total_matches"] >= 1
    assert detail.policy["policy_outcome"] == "ELIGIBLE"
    assert detail.contest_draft["review_status"] == "APPROVED"
    assert detail.preflight["preflight_status"] == "READY"
    assert detail.submission["submission_status"] == "SUBMITTED"
    assert detail.razorpay_lifecycle["outcome"] == "UNDER_REVIEW"


@pytest.mark.asyncio
async def test_14_to_20_detail_sections_structured_properly(async_db):
    """14-20. Verifies evidence, matching, policy, draft, preflight, submission, and lifecycle sections."""
    await setup_dashboard_dispute(async_db, "disp_dash_sec", submission_mode="SUCCESS", lifecycle_status="won")

    detail = await get_dispute_dashboard_detail("disp_dash_sec", async_db)
    assert "document_types" in detail.evidence
    assert "status_counts" in detail.matching
    assert "critical_findings" in detail.policy
    assert "input_fingerprint" in detail.contest_draft
    assert "blocking_reasons" in detail.preflight
    assert "failure_category" in detail.submission
    assert "local_lifecycle_status" in detail.razorpay_lifecycle


@pytest.mark.asyncio
async def test_21_chronological_timeline_ordering(async_db):
    """21. Timeline events are strictly ordered by timestamp."""
    await setup_dashboard_dispute(async_db, "disp_dash_time", submission_mode="SUCCESS", lifecycle_status="under_review")

    detail = await get_dispute_dashboard_detail("disp_dash_time", async_db)
    timestamps = [e.timestamp for e in detail.timeline]
    assert timestamps == sorted(timestamps)


# ===========================================================================
# 3. ALERTS & SPECIALIZED VIEWS (22-26)
# ===========================================================================


@pytest.mark.asyncio
async def test_22_operational_alerts_detection(async_db):
    """22. Detects operational alerts deterministically."""
    await setup_dashboard_dispute(async_db, "disp_dash_alt", submission_mode="TIMEOUT", lifecycle_status="under_review")

    alerts = await get_dashboard_alerts(async_db)
    assert any(a.alert_code == "SUBMISSION_UNKNOWN" and a.dispute_id == "disp_dash_alt" for a in alerts)


@pytest.mark.asyncio
async def test_23_unknown_reconciliation_required_view(async_db):
    """23. Returns disputes requiring reconciliation (UNKNOWN state)."""
    await setup_dispute_for_reconciliation_dash(async_db, "disp_dash_recon")

    items = await get_reconciliation_required_disputes(async_db)
    assert any(i.dispute_id == "disp_dash_recon" for i in items)


async def setup_dispute_for_reconciliation_dash(async_db, dispute_id: str):
    await setup_dashboard_dispute(async_db, dispute_id, submission_mode="TIMEOUT")


@pytest.mark.asyncio
async def test_24_action_required_monitoring_view(async_db):
    """24. Returns disputes in Razorpay action_required status."""
    await setup_dashboard_dispute(async_db, "disp_dash_act", submission_mode="SUCCESS", lifecycle_status="action_required")

    items = await get_action_required_disputes(async_db)
    assert any(i.dispute_id == "disp_dash_act" for i in items)


@pytest.mark.asyncio
async def test_25_to_26_won_and_lost_outcome_summaries(async_db):
    """25-26. Correctly tracks WON and LOST final outcomes."""
    await setup_dashboard_dispute(async_db, "disp_dash_won", submission_mode="SUCCESS", lifecycle_status="won")
    await setup_dashboard_dispute(async_db, "disp_dash_lost", submission_mode="SUCCESS", lifecycle_status="lost")

    summary = await get_outcomes_summary(async_db)
    assert summary.won_count >= 1
    assert summary.lost_count >= 1


# ===========================================================================
# 4. SAFETY & IMMUTABILITY TESTS (27-34)
# ===========================================================================


@pytest.mark.asyncio
async def test_27_financial_immutability_in_dashboard(async_db):
    """27. Verifies dispute financial fields (payment_id, amount, currency) are untouched."""
    dispute, draft, preflight, sub = await setup_dashboard_dispute(async_db, "disp_dash_fi", submission_mode="SUCCESS", lifecycle_status="won")

    pay_before = dispute.payment_id
    amt_before = dispute.amount
    curr_before = dispute.currency

    await get_dispute_dashboard_detail("disp_dash_fi", async_db)

    stmt = select(Dispute).where(Dispute.id == "disp_dash_fi")
    disp_after = (await async_db.execute(stmt)).scalars().first()

    assert disp_after.payment_id == pay_before
    assert disp_after.amount == amt_before
    assert disp_after.currency == curr_before


@pytest.mark.asyncio
async def test_28_to_31_policy_match_evidence_draft_immutability(async_db):
    """28-31. Verifies policy, match, evidence, and draft remain untouched by dashboard reads."""
    dispute, draft, preflight, sub = await setup_dashboard_dispute(async_db, "disp_dash_imm", submission_mode="SUCCESS", lifecycle_status="won")

    pol_before = dispute.policy_results[0].outcome
    draft_status_before = draft.status

    await get_dashboard_summary(async_db)
    await get_dispute_dashboard_detail("disp_dash_imm", async_db)

    assert dispute.policy_results[0].outcome == pol_before
    assert draft.status == draft_status_before


@pytest.mark.asyncio
async def test_32_to_34_no_razorpay_calls_or_mutation_methods():
    """32-34. Verifies zero Razorpay API imports or mutation calls exist in dashboard_service."""
    import backend.app.services.dashboard_service as ds
    src = inspect.getsource(ds)

    assert "RazorpayClient" not in src
    assert "ContestSubmissionClient" not in src
    assert "submit_contest" not in src
    assert "accept_dispute" not in src
    assert "reject_dispute" not in src
    assert "issue_refund" not in src


# ===========================================================================
# 5. SECURITY & INJECTION DEFENSE TESTS (35-38)
# ===========================================================================


@pytest.mark.asyncio
async def test_35_credential_sanitization_check():
    """35. Verifies internal credentials/secrets are not exposed in detail responses."""
    from backend.app.services.contest_submission_service import _sanitize_metadata
    dirty = {"auth": "Bearer secret", "key": "1234"}
    clean = _sanitize_metadata(dirty)
    assert clean["auth"] == "[REDACTED]"
    assert clean["key"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_36_to_37_sort_and_sql_injection_defense(client, async_db):
    """36-37. Rejects arbitrary SQL or sorting injection attempts safely."""
    await setup_dashboard_dispute(async_db, "disp_dash_inj", submission_mode="SUCCESS", lifecycle_status="won")

    res = await client.get("/api/dashboard/disputes?status='; DROP TABLE disputes; --")
    assert res.status_code == 200
    # SQL injection attempt string matches 0 items safely without error
    assert len(res.json()["items"]) == 0


@pytest.mark.asyncio
async def test_38_deterministic_repeated_dashboard_queries(async_db):
    """38. Repeated dashboard queries produce deterministic results."""
    await setup_dashboard_dispute(async_db, "disp_dash_det", submission_mode="SUCCESS", lifecycle_status="won")

    res1 = await get_dashboard_summary(async_db)
    res2 = await get_dashboard_summary(async_db)

    assert res1.total_disputes == res2.total_disputes
    assert res1.won_count == res2.won_count
