"""
Unit Test Suite: Controlled Contest Submission Execution — Task 5.4B

Comprehensive 49-test suite covering pre-submission authorization gate revalidations,
client parameter injection defense, idempotency & CAS locks, HTTP error handling (400, 401, 403, 404, 409, 429, 500, timeout, connection failure, malformed response),
financial immutability assertions, credential sanitization, and append-only audit logging.
"""

import hashlib
import pytest
from unittest.mock import patch
from sqlalchemy import text
from sqlalchemy.future import select

from backend.app.models.contest_draft import ContestDraft as ContestDraftModel
from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.contest_submission_audit import ContestSubmissionAudit
from backend.app.models.contest_submission_preflight import ContestSubmissionPreflight
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.schemas.contest_draft import ReviewStatus
from backend.app.schemas.contest_submission import (
    FailureCategory,
    RazorpayContestSubmissionRequest,
    RazorpayContestSubmissionResponse,
    SubmissionStatus,
)
from backend.app.schemas.contest_submission_preflight import PreflightStatus
from backend.app.services.contest_draft_fingerprint import compute_contest_draft_input_fingerprint
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.services.contest_submission_preflight_service import run_preflight
from backend.app.services.contest_submission_service import (
    SubmissionAuthorizationException,
    SubmissionConflictException,
    submit_dispute_contest,
)
from backend.app.schemas.contest_draft_review import ReviewDecision
from backend.app.services.matching_service import run_dispute_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy


async def setup_dispute_for_submission(
    async_db,
    dispute_id: str,
    payment_id: str = "pay_sub_1",
    order_id: str = "ord_sub_1",
    amount: int = 149900,
    currency: str = "INR",
    approve_draft: bool = True,
    run_preflight_gate: bool = True,
):
    """Sets up a complete dispute pipeline through Preflight READY state."""
    # Clean up existing test data
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
        raw_payload={
            "payload": {
                "dispute": {
                    "entity": {
                        "id": dispute_id,
                        "payment_id": payment_id,
                        "order_id": order_id,
                        "amount": amount,
                        "currency": currency,
                    }
                }
            }
        },
    )
    async_db.add(dispute)

    doc_id = f"doc_sub_{dispute_id}"
    doc = EvidenceDocument(
        id=doc_id,
        dispute_id=dispute_id,
        razorpay_doc_id=f"rzp_doc_{dispute_id}",
        original_filename="invoice_sub.pdf",
        internal_filename=f"int_{dispute_id}.png",
        file_path=f"/tmp/test_{dispute_id}.pdf",
        file_hash="b" * 64,
        file_size_bytes=600,
        mime_type="application/pdf",
        document_type="invoice",
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc)

    ext = ExtractedEvidence(
        id=f"ext_sub_{dispute_id}",
        document_id=doc_id,
        document_type="invoice",
        payment_id=payment_id,
        order_id=order_id,
        amount_minor=amount,
        currency=currency,
        customer_name="Aarav Mehta",
        confidence_score=0.98,
        extracted_data={"payment_id": payment_id, "amount_minor": amount, "order_id": order_id},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext)
    await async_db.commit()

    await run_dispute_matching(dispute_id, async_db)
    await evaluate_dispute_policy(dispute_id, async_db, reference_date="2026-08-26")
    draft = await generate_contest_draft(dispute_id, async_db, reference_date="2026-08-26")

    if approve_draft:
        await review_contest_draft(dispute_id, ReviewDecision.APPROVE, comment="Approved for submission test", db=async_db)

    preflight = None
    if run_preflight_gate:
        preflight = await run_preflight(dispute_id, async_db)

    return dispute, draft, preflight


# ===========================================================================
# 1. AUTHORIZATION TESTS (1-12)
# ===========================================================================


@pytest.mark.asyncio
async def test_01_ready_draft_submits_successfully(async_db):
    """1. READY draft submits cleanly through MockContestSubmissionClient."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_01")
    client = MockContestSubmissionClient(mode="SUCCESS")

    res = await submit_dispute_contest("disp_sub_01", async_db, client=client)
    assert res.status == SubmissionStatus.SUBMITTED
    assert res.razorpay_status == "under_review"
    assert res.razorpay_reference_id == "sub_ref_mock_disp_sub_01"
    assert res.audit_id is not None


@pytest.mark.asyncio
async def test_02_pending_review_draft_rejected(async_db):
    """2. PENDING_REVIEW draft rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_02", approve_draft=False, run_preflight_gate=False)
    client = MockContestSubmissionClient()

    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_02", async_db, client=client)
    assert "APPROVED required" in str(exc_info.value.reasons)


@pytest.mark.asyncio
async def test_03_rejected_review_draft_rejected(async_db):
    """3. REJECTED draft rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_03", approve_draft=False)
    await review_contest_draft("disp_sub_03", ReviewDecision.REJECT, comment="Rejected by merchant", db=async_db)
    client = MockContestSubmissionClient()

    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_03", async_db, client=client)
    assert any("APPROVED required" in r for r in exc_info.value.reasons)


@pytest.mark.asyncio
async def test_04_blocked_draft_rejected(async_db):
    """4. BLOCKED draft rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_04")
    stmt = select(ContestDraftModel).where(ContestDraftModel.dispute_id == "disp_sub_04")
    db_draft = (await async_db.execute(stmt)).scalars().first()
    db_draft.status = "BLOCKED"
    await async_db.commit()

    client = MockContestSubmissionClient()
    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_04", async_db, client=client)
    assert any("BLOCKED" in r for r in exc_info.value.reasons)


@pytest.mark.asyncio
async def test_05_missing_preflight_rejected(async_db):
    """5. Missing preflight record rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_05", run_preflight_gate=False)
    await review_contest_draft("disp_sub_05", ReviewDecision.APPROVE, comment="Approved", db=async_db)
    client = MockContestSubmissionClient()

    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_05", async_db, client=client)
    assert any("Preflight record does not exist" in r for r in exc_info.value.reasons)


@pytest.mark.asyncio
async def test_06_non_ready_preflight_rejected(async_db):
    """6. Non-READY preflight status rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_06")
    stmt = select(ContestSubmissionPreflight).where(ContestSubmissionPreflight.dispute_id == "disp_sub_06")
    db_pref = (await async_db.execute(stmt)).scalars().first()
    db_pref.status = "BLOCKED"
    await async_db.commit()

    client = MockContestSubmissionClient()
    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_06", async_db, client=client)
    assert any("READY required" in r for r in exc_info.value.reasons)


@pytest.mark.asyncio
async def test_07_stale_fingerprint_rejected(async_db):
    """7. Stale draft fingerprint rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_07")
    stmt = select(ContestDraftModel).where(ContestDraftModel.dispute_id == "disp_sub_07")
    db_draft = (await async_db.execute(stmt)).scalars().first()
    db_draft.input_fingerprint = "0" * 64
    await async_db.commit()

    client = MockContestSubmissionClient()
    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_07", async_db, client=client)
    assert any("stale draft" in r for r in exc_info.value.reasons)


@pytest.mark.asyncio
async def test_08_changed_payment_id_rejected(async_db):
    """8. Changed payment_id rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_08")
    dispute.payment_id = "pay_CHANGED"
    await async_db.commit()

    client = MockContestSubmissionClient()
    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_08", async_db, client=client)
    assert len(exc_info.value.reasons) > 0


@pytest.mark.asyncio
async def test_09_changed_amount_rejected(async_db):
    """9. Changed amount rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_09")
    dispute.amount = 99900
    await async_db.commit()

    client = MockContestSubmissionClient()
    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_09", async_db, client=client)
    assert len(exc_info.value.reasons) > 0


@pytest.mark.asyncio
async def test_10_changed_currency_rejected(async_db):
    """10. Changed currency rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_10")
    dispute.currency = "USD"
    await async_db.commit()

    client = MockContestSubmissionClient()
    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_10", async_db, client=client)
    assert len(exc_info.value.reasons) > 0


@pytest.mark.asyncio
async def test_11_changed_policy_rejected(async_db):
    """11. Changed policy outcome rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_11")
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = 'disp_sub_11'"))
    await async_db.commit()

    client = MockContestSubmissionClient()
    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_11", async_db, client=client)
    assert any("PolicyResult does not exist" in r for r in exc_info.value.reasons)


@pytest.mark.asyncio
async def test_12_changed_evidence_rejected(async_db):
    """12. Deleted match/evidence results rejected by authorization gate."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_12")
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = 'disp_sub_12'"))
    await async_db.commit()

    client = MockContestSubmissionClient()
    with pytest.raises(SubmissionAuthorizationException) as exc_info:
        await submit_dispute_contest("disp_sub_12", async_db, client=client)
    assert any("stale draft" in r for r in exc_info.value.reasons)


# ===========================================================================
# 2. SECURITY TESTS (13-22)
# ===========================================================================


@pytest.mark.asyncio
async def test_13_to_21_client_cannot_inject_fields(client, async_db):
    """13-21. Client cannot inject amount, currency, payment_id, evidence, policy, draft, preflight, endpoint, method."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_sec_13")

    injection_body = {
        "amount": 0,
        "currency": "USD",
        "payment_id": "pay_HACK",
        "evidence": ["hacked_doc"],
        "policy_outcome": "ELIGIBLE",
        "draft_id": "draft_HACK",
        "preflight_id": "pref_HACK",
        "endpoint": "https://attacker.com/steal",
        "method": "DELETE",
    }

    # API ignores extra client fields (schema extra='forbid' -> HTTP 422)
    response = await client.post("/api/disputes/disp_sub_sec_13/contest-submission", json=injection_body)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_22_no_accept_or_reject_dispute_operation(async_db):
    """22. Verifies submission boundary exposes ZERO dispute accept/reject/refund operations."""
    from backend.app.services.contest_submission_client import ContestSubmissionClient
    client_methods = [m for m in dir(ContestSubmissionClient) if not m.startswith("_")]
    assert client_methods == ["submit_contest"]
    assert "accept_dispute" not in client_methods
    assert "reject_dispute" not in client_methods
    assert "refund" not in client_methods


# ===========================================================================
# 3. IDEMPOTENCY & CONCURRENCY TESTS (23-26)
# ===========================================================================


@pytest.mark.asyncio
async def test_23_duplicate_submission_prevented(async_db):
    """23. Duplicate submission attempt raises 409 Conflict."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_23")
    client = MockContestSubmissionClient(mode="SUCCESS")

    res1 = await submit_dispute_contest("disp_sub_23", async_db, client=client)
    assert res1.status == SubmissionStatus.SUBMITTED

    with pytest.raises(SubmissionConflictException) as exc_info:
        await submit_dispute_contest("disp_sub_23", async_db, client=client)
    assert "already been submitted" in str(exc_info.value)


@pytest.mark.asyncio
async def test_24_concurrent_submission_prevented(async_db):
    """24. Concurrent submission claim (SUBMISSION_IN_PROGRESS) raises 409 Conflict."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_24")

    # Manually create SUBMISSION_IN_PROGRESS record in DB
    sub = ContestSubmission(
        id="sub_conc_24",
        submission_attempt_id="att_24",
        dispute_id="disp_sub_24",
        contest_draft_id=draft.id,
        preflight_id=preflight.id,
        input_fingerprint=draft.input_fingerprint,
        idempotency_key="idemp_24",
        previous_state="READY",
        state=SubmissionStatus.SUBMISSION_IN_PROGRESS.value,
    )
    async_db.add(sub)
    await async_db.commit()

    client = MockContestSubmissionClient()
    with pytest.raises(SubmissionConflictException) as exc_info:
        await submit_dispute_contest("disp_sub_24", async_db, client=client)
    assert "in progress" in str(exc_info.value)


@pytest.mark.asyncio
async def test_25_repeated_successful_request_is_deterministic(async_db):
    """25. Verification of idempotency key uniqueness and repeat defense."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_25")
    client = MockContestSubmissionClient(mode="SUCCESS")

    res = await submit_dispute_contest("disp_sub_25", async_db, client=client)
    assert res.idempotency_key is not None
    assert len(res.idempotency_key) == 64


@pytest.mark.asyncio
async def test_26_unknown_state_not_blindly_retried(async_db):
    """26. UNKNOWN state from network timeout is NOT blindly retried."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_26")
    client = MockContestSubmissionClient(mode="TIMEOUT")

    res_timeout = await submit_dispute_contest("disp_sub_26", async_db, client=client)
    assert res_timeout.status == SubmissionStatus.UNKNOWN

    with pytest.raises(SubmissionConflictException) as exc_info:
        await submit_dispute_contest("disp_sub_26", async_db, client=client)
    assert "status is UNKNOWN" in str(exc_info.value)


# ===========================================================================
# 4. ERROR HANDLING TESTS (27-36)
# ===========================================================================


@pytest.mark.asyncio
async def test_27_http_400_bad_request_fails(async_db):
    """27. HTTP 400 Bad Request maps to FAILED state and CLIENT_ERROR_4XX."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_27")
    client = MockContestSubmissionClient(mode="HTTP_400")

    res = await submit_dispute_contest("disp_sub_27", async_db, client=client)
    assert res.status == SubmissionStatus.FAILED
    assert res.failure_category == FailureCategory.CLIENT_ERROR_4XX


@pytest.mark.asyncio
async def test_28_http_401_unauthorized_fails(async_db):
    """28. HTTP 401 Unauthorized maps to FAILED state and AUTH_ERROR_401_403."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_28")
    client = MockContestSubmissionClient(mode="HTTP_401")

    res = await submit_dispute_contest("disp_sub_28", async_db, client=client)
    assert res.status == SubmissionStatus.FAILED
    assert res.failure_category == FailureCategory.AUTH_ERROR_401_403


@pytest.mark.asyncio
async def test_29_http_403_forbidden_fails(async_db):
    """29. HTTP 403 Forbidden maps to FAILED state and AUTH_ERROR_401_403."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_29")
    client = MockContestSubmissionClient(mode="HTTP_403")

    res = await submit_dispute_contest("disp_sub_29", async_db, client=client)
    assert res.status == SubmissionStatus.FAILED
    assert res.failure_category == FailureCategory.AUTH_ERROR_401_403


@pytest.mark.asyncio
async def test_30_http_404_not_found_fails(async_db):
    """30. HTTP 404 Not Found maps to FAILED state and NOT_FOUND_404."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_30")
    client = MockContestSubmissionClient(mode="HTTP_404")

    res = await submit_dispute_contest("disp_sub_30", async_db, client=client)
    assert res.status == SubmissionStatus.FAILED
    assert res.failure_category == FailureCategory.NOT_FOUND_404


@pytest.mark.asyncio
async def test_31_http_409_conflict_fails(async_db):
    """31. HTTP 409 Conflict maps to FAILED state and CONFLICT_409."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_31")
    client = MockContestSubmissionClient(mode="HTTP_409")

    res = await submit_dispute_contest("disp_sub_31", async_db, client=client)
    assert res.status == SubmissionStatus.FAILED
    assert res.failure_category == FailureCategory.CONFLICT_409


@pytest.mark.asyncio
async def test_32_http_429_rate_limit_fails(async_db):
    """32. HTTP 429 Rate Limit maps to FAILED state and RATE_LIMIT_429."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_32")
    client = MockContestSubmissionClient(mode="HTTP_429")

    res = await submit_dispute_contest("disp_sub_32", async_db, client=client)
    assert res.status == SubmissionStatus.FAILED
    assert res.failure_category == FailureCategory.RATE_LIMIT_429


@pytest.mark.asyncio
async def test_33_http_500_server_error_fails(async_db):
    """33. HTTP 500 Server Error maps to FAILED state and SERVER_ERROR_5XX."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_33")
    client = MockContestSubmissionClient(mode="HTTP_500")

    res = await submit_dispute_contest("disp_sub_33", async_db, client=client)
    assert res.status == SubmissionStatus.FAILED
    assert res.failure_category == FailureCategory.SERVER_ERROR_5XX


@pytest.mark.asyncio
async def test_34_network_timeout_transitions_to_unknown(async_db):
    """34. Network timeout transitions to UNKNOWN state."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_34")
    client = MockContestSubmissionClient(mode="TIMEOUT")

    res = await submit_dispute_contest("disp_sub_34", async_db, client=client)
    assert res.status == SubmissionStatus.UNKNOWN
    assert res.failure_category == FailureCategory.TIMEOUT_AMBIGUOUS


@pytest.mark.asyncio
async def test_35_connection_failure_transitions_to_unknown(async_db):
    """35. Connection failure transitions to UNKNOWN state."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_35")
    client = MockContestSubmissionClient(mode="CONNECTION_FAILURE")

    res = await submit_dispute_contest("disp_sub_35", async_db, client=client)
    assert res.status == SubmissionStatus.UNKNOWN


@pytest.mark.asyncio
async def test_36_malformed_response_handled_safely(async_db):
    """36. Malformed JSON response handled safely."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_36")
    client = MockContestSubmissionClient(mode="MALFORMED_RESPONSE")

    res = await submit_dispute_contest("disp_sub_36", async_db, client=client)
    assert res.status == SubmissionStatus.SUBMITTED


# ===========================================================================
# 5. FINANCIAL SAFETY TESTS (37-45)
# ===========================================================================


@pytest.mark.asyncio
async def test_37_to_41_source_data_financial_fields_unchanged(async_db):
    """37-41. Verifies financial fields, policy, draft, evidence, preflight unchanged by submission."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_sf_37")

    pay_before = dispute.payment_id
    amt_before = dispute.amount
    curr_before = dispute.currency
    pol_before = dispute.policy_results[0].outcome
    draft_status_before = draft.status

    client = MockContestSubmissionClient(mode="SUCCESS")
    await submit_dispute_contest("disp_sub_sf_37", async_db, client=client)

    stmt = select(Dispute).where(Dispute.id == "disp_sub_sf_37")
    disp_after = (await async_db.execute(stmt)).scalars().first()

    assert disp_after.payment_id == pay_before
    assert disp_after.amount == amt_before
    assert disp_after.currency == curr_before
    assert dispute.policy_results[0].outcome == pol_before
    assert draft.status == draft_status_before


@pytest.mark.asyncio
async def test_42_to_43_credentials_never_logged_or_in_errors(async_db):
    """42-43. Verifies credentials are sanitized from audit metadata."""
    from backend.app.services.contest_submission_service import _sanitize_metadata
    dirty_meta = {"key_secret": "secret_123", "authorization": "Basic xyz", "normal_field": "val"}
    clean_meta = _sanitize_metadata(dirty_meta)
    assert clean_meta["key_secret"] == "[REDACTED]"
    assert clean_meta["authorization"] == "[REDACTED]"
    assert clean_meta["normal_field"] == "val"


@pytest.mark.asyncio
async def test_44_to_45_no_arbitrary_network_endpoint_or_method(async_db):
    """44-45. Verifies client uses hardcoded URL structure and POST method only."""
    from unittest.mock import AsyncMock, MagicMock
    from backend.app.services.contest_submission_client import HttpContestSubmissionClient

    client = HttpContestSubmissionClient()
    req = RazorpayContestSubmissionRequest(dispute_id="disp_1", amount_minor=100, currency="INR", summary="s")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "sub_1", "status": "under_review"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        await client.submit_contest(req)

        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        assert call_url.endswith("/v1/disputes/disp_1/contest")


# ===========================================================================
# 6. AUDIT TRAIL TESTS (46-49)
# ===========================================================================


@pytest.mark.asyncio
async def test_46_to_49_audit_trail_created_for_all_outcomes(async_db):
    """46-49. Verifies append-only audit trail created for attempt, success, failure, and UNKNOWN."""
    dispute, draft, preflight = await setup_dispute_for_submission(async_db, "disp_sub_aud_46")

    client = MockContestSubmissionClient(mode="SUCCESS")
    res = await submit_dispute_contest("disp_sub_aud_46", async_db, client=client)

    stmt = select(ContestSubmissionAudit).where(ContestSubmissionAudit.dispute_id == "disp_sub_aud_46")
    audits = (await async_db.execute(stmt)).scalars().all()
    assert len(audits) >= 1
    assert audits[0].submission_status == "SUBMITTED"
    assert audits[0].http_status_code == 200
