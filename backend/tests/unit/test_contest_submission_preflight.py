"""
Unit Test Suite: Contest Submission Preflight & Local Authorization Gate — Task 5.3

Verifies preflight decision model (READY, BLOCKED, STALE, INVALID, REVIEW_REQUIRED),
fingerprint validation, financial immutability, evidence provenance checks, policy consistency,
audit trails, zero AI/Razorpay mutations, and API contracts.
"""

import pytest
from unittest.mock import patch
from sqlalchemy import text
from sqlalchemy.future import select

from backend.app.models.contest_draft import ContestDraft as ContestDraftModel
from backend.app.models.contest_submission_preflight import ContestSubmissionPreflight
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.matching import MatchResult
from backend.app.models.policy import PolicyResult
from backend.app.schemas.contest_submission_preflight import PreflightStatus, CheckStatus
from backend.app.services.contest_draft_fingerprint import compute_contest_draft_input_fingerprint
from backend.app.services.contest_draft_review_service import review_contest_draft
from backend.app.services.contest_draft_service import generate_contest_draft
from backend.app.services.contest_submission_preflight_service import (
    StaleDraftException,
    run_preflight,
)
from backend.app.schemas.contest_draft_review import ReviewDecision
from backend.app.services.matching_service import run_dispute_matching
from backend.app.services.policy_engine_service import evaluate_dispute_policy


async def setup_dispute_for_preflight(
    async_db,
    dispute_id: str,
    payment_id: str = "pay_pref_1",
    order_id: str = "ord_pref_1",
    amount: int = 149900,
    currency: str = "INR",
    extracted_data: dict = None,
    doc_type: str = "invoice",
):
    """Sets up a complete dispute pipeline (dispute, doc, extraction, match, policy, draft) for preflight testing."""
    # Clean up existing test data for this dispute_id
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

    doc_id = f"doc_pref_{dispute_id}"
    doc = EvidenceDocument(
        id=doc_id,
        dispute_id=dispute_id,
        razorpay_doc_id=f"rzp_doc_{dispute_id}",
        original_filename="test_inv.pdf",
        internal_filename=f"int_{dispute_id}.png",
        file_path=f"/tmp/test_{dispute_id}.pdf",
        file_hash="a" * 64,
        file_size_bytes=500,
        mime_type="application/pdf",
        document_type=doc_type,
        processing_status="AI_EXTRACTED",
    )
    async_db.add(doc)

    ext_payload = extracted_data or {
        "payment_id": payment_id,
        "order_id": order_id,
        "amount_minor": amount,
        "currency": currency,
        "customer_name": "Gaurav Sharma",
        "document_type": doc_type,
    }

    ext = ExtractedEvidence(
        id=f"ext_pref_{dispute_id}",
        document_id=doc_id,
        document_type=doc_type,
        payment_id=ext_payload.get("payment_id"),
        order_id=ext_payload.get("order_id"),
        amount_minor=ext_payload.get("amount_minor"),
        currency=ext_payload.get("currency"),
        customer_name=ext_payload.get("customer_name"),
        confidence_score=0.95,
        confidence_by_field={"payment_id": "HIGH", "order_id": "HIGH", "amount_minor": "HIGH"},
        extracted_data={"raw_llm_json": ext_payload},
        schema_version="1.0",
        model_name="mock-vision-v1",
    )
    async_db.add(ext)
    await async_db.commit()

    # Matcher
    await run_dispute_matching(dispute_id, async_db)
    # Policy
    await evaluate_dispute_policy(dispute_id, async_db, reference_date="2026-08-26")
    # Draft
    draft = await generate_contest_draft(dispute_id, async_db, reference_date="2026-08-26")
    return dispute, draft


# --- Test 1: APPROVED + Valid Draft -> READY ---
@pytest.mark.asyncio
async def test_preflight_approved_valid_draft_returns_ready(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t1")
    await review_contest_draft("disp_pref_t1", ReviewDecision.APPROVE, comment="Approved for test", db=async_db)

    res = await run_preflight("disp_pref_t1", async_db)
    assert res.status == PreflightStatus.READY
    assert res.review_status == "APPROVED"
    assert res.draft_status in ["DRAFT", "REVIEW_REQUIRED"]
    assert len(res.blocking_reasons) == 0


# --- Test 2: PENDING_REVIEW -> REVIEW_REQUIRED ---
@pytest.mark.asyncio
async def test_preflight_pending_review_returns_review_required(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t2")

    res = await run_preflight("disp_pref_t2", async_db)
    assert res.status == PreflightStatus.REVIEW_REQUIRED
    assert res.review_status == "PENDING_REVIEW"
    assert any("APPROVED required" in r for r in res.blocking_reasons)


# --- Test 3: REJECTED -> REVIEW_REQUIRED ---
@pytest.mark.asyncio
async def test_preflight_rejected_review_returns_review_required(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t3")
    await review_contest_draft("disp_pref_t3", ReviewDecision.REJECT, comment="Rejected by reviewer", db=async_db)

    res = await run_preflight("disp_pref_t3", async_db)
    assert res.status == PreflightStatus.REVIEW_REQUIRED
    assert res.review_status == "REJECTED"


# --- Test 4: BLOCKED Draft -> BLOCKED ---
@pytest.mark.asyncio
async def test_preflight_blocked_draft_returns_blocked(async_db):
    # Set up with mismatched payment_id to force BLOCKED policy status
    dispute, draft = await setup_dispute_for_preflight(
        async_db, "disp_pref_t4", extracted_data={"payment_id": "pay_WRONG", "order_id": "ord_pref_1", "amount_minor": 149900}
    )

    res = await run_preflight("disp_pref_t4", async_db)
    assert res.status == PreflightStatus.BLOCKED
    assert res.draft_status == "BLOCKED"
    assert any("BLOCKED" in r for r in res.blocking_reasons)


# --- Test 5: Stale Fingerprint -> STALE / 409 ---
@pytest.mark.asyncio
async def test_preflight_stale_fingerprint_raises_exception(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t5")
    # Mutate draft fingerprint in DB to simulate stale draft
    stmt = select(ContestDraftModel).where(ContestDraftModel.dispute_id == "disp_pref_t5")
    db_draft = (await async_db.execute(stmt)).scalars().first()
    db_draft.input_fingerprint = "0" * 64
    await async_db.commit()

    with pytest.raises(StaleDraftException) as exc_info:
        await run_preflight("disp_pref_t5", async_db)
    assert "Draft is stale" in str(exc_info.value)


# --- Test 6: Changed payment_id -> Stale / Blocked ---
@pytest.mark.asyncio
async def test_preflight_changed_payment_id_returns_blocked(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t6")
    await review_contest_draft("disp_pref_t6", ReviewDecision.APPROVE, comment="Approved", db=async_db)

    # Mutate dispute payment_id
    dispute.payment_id = ""
    await async_db.commit()

    # Changing payment_id alters input fingerprint -> StaleDraftException
    with pytest.raises(StaleDraftException):
        await run_preflight("disp_pref_t6", async_db)


# --- Test 7: Changed amount -> Stale / Blocked ---
@pytest.mark.asyncio
async def test_preflight_changed_amount_returns_blocked(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t7")
    await review_contest_draft("disp_pref_t7", ReviewDecision.APPROVE, comment="Approved", db=async_db)

    dispute.amount = -100
    await async_db.commit()

    with pytest.raises(StaleDraftException):
        await run_preflight("disp_pref_t7", async_db)


# --- Test 8: Changed currency -> Stale / Blocked ---
@pytest.mark.asyncio
async def test_preflight_changed_currency_returns_blocked(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t8")
    await review_contest_draft("disp_pref_t8", ReviewDecision.APPROVE, comment="Approved", db=async_db)

    dispute.currency = ""
    await async_db.commit()

    with pytest.raises(StaleDraftException):
        await run_preflight("disp_pref_t8", async_db)


# --- Test 9: Missing PolicyResult -> BLOCKED ---
@pytest.mark.asyncio
async def test_preflight_missing_policy_result_returns_blocked(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t9")
    await async_db.execute(text("DELETE FROM policy_results WHERE dispute_id = 'disp_pref_t9'"))
    await async_db.commit()

    # Update draft fingerprint to match state without policy_result
    stmt = select(ContestDraftModel).where(ContestDraftModel.dispute_id == "disp_pref_t9")
    db_draft = (await async_db.execute(stmt)).scalars().first()
    db_draft.input_fingerprint = compute_contest_draft_input_fingerprint(
        dispute_id="disp_pref_t9",
        payment_id=dispute.payment_id,
        amount=dispute.amount,
        currency=dispute.currency,
        policy_result_id=None,
        policy_version=None,
        policy_outcome=None,
        match_results=list(dispute.match_results),
        documents=list(dispute.documents),
    )
    await async_db.commit()

    res = await run_preflight("disp_pref_t9", async_db)
    assert res.status == PreflightStatus.BLOCKED
    assert any("Missing PolicyResult" in r for r in res.blocking_reasons)


# --- Test 10: Inconsistent PolicyResult -> BLOCKED ---
@pytest.mark.asyncio
async def test_preflight_inconsistent_policy_result_returns_blocked(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t10")
    stmt = select(PolicyResult).where(PolicyResult.dispute_id == "disp_pref_t10")
    pol = (await async_db.execute(stmt)).scalars().first()
    pol.outcome = "NOT_ELIGIBLE"

    stmt_d = select(ContestDraftModel).where(ContestDraftModel.dispute_id == "disp_pref_t10")
    db_draft = (await async_db.execute(stmt_d)).scalars().first()
    db_draft.input_fingerprint = compute_contest_draft_input_fingerprint(
        dispute_id="disp_pref_t10",
        payment_id=dispute.payment_id,
        amount=dispute.amount,
        currency=dispute.currency,
        policy_result_id=pol.id,
        policy_version=pol.policy_version,
        policy_outcome=pol.outcome,
        match_results=list(dispute.match_results),
        documents=list(dispute.documents),
    )
    await async_db.commit()

    res = await run_preflight("disp_pref_t10", async_db)
    assert res.status == PreflightStatus.BLOCKED
    assert any("NOT_ELIGIBLE" in r for r in res.blocking_reasons)


# --- Test 11: Missing MatchResult -> STALE or BLOCKED ---
@pytest.mark.asyncio
async def test_preflight_missing_match_results_returns_blocked(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t11")
    await async_db.execute(text("DELETE FROM match_results WHERE dispute_id = 'disp_pref_t11'"))
    await async_db.commit()

    with pytest.raises(StaleDraftException):
        await run_preflight("disp_pref_t11", async_db)


# --- Test 12: Missing Evidence Provenance -> BLOCKED ---
@pytest.mark.asyncio
async def test_preflight_missing_evidence_provenance_returns_blocked(async_db):
    from sqlalchemy.orm.attributes import flag_modified

    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t12")
    await review_contest_draft("disp_pref_t12", ReviewDecision.APPROVE, comment="Approved", db=async_db)

    stmt = select(ContestDraftModel).where(ContestDraftModel.dispute_id == "disp_pref_t12")
    db_draft = (await async_db.execute(stmt)).scalars().first()

    factual_args_dict = dict(db_draft.factual_arguments or {})
    args_list = factual_args_dict.get("arguments", [])
    if args_list:
        args_list[0]["source_evidence_ids"] = ["doc_NONEXISTENT_999"]
        factual_args_dict["arguments"] = args_list
        db_draft.factual_arguments = factual_args_dict
        flag_modified(db_draft, "factual_arguments")
        await async_db.commit()

    res = await run_preflight("disp_pref_t12", async_db)
    assert res.status == PreflightStatus.BLOCKED
    assert any("provenance" in r for r in res.blocking_reasons)


# --- Test 13: Invalid Evidence Source Match ID -> BLOCKED ---
@pytest.mark.asyncio
async def test_preflight_invalid_source_match_id_returns_blocked(async_db):
    from sqlalchemy.orm.attributes import flag_modified

    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t13")
    await review_contest_draft("disp_pref_t13", ReviewDecision.APPROVE, comment="Approved", db=async_db)

    stmt = select(ContestDraftModel).where(ContestDraftModel.dispute_id == "disp_pref_t13")
    db_draft = (await async_db.execute(stmt)).scalars().first()

    factual_args_dict = dict(db_draft.factual_arguments or {})
    args_list = factual_args_dict.get("arguments", [])
    if args_list:
        args_list[0]["source_match_result_ids"] = ["match_INVALID_999"]
        factual_args_dict["arguments"] = args_list
        db_draft.factual_arguments = factual_args_dict
        flag_modified(db_draft, "factual_arguments")
        await async_db.commit()

    res = await run_preflight("disp_pref_t13", async_db)
    assert res.status == PreflightStatus.BLOCKED
    assert any("provenance" in r for r in res.blocking_reasons)


# --- Test 14: Critical Mismatch Check ---
@pytest.mark.asyncio
async def test_preflight_critical_mismatch_check(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t14")
    m = MatchResult(
        id="match_crit_fail",
        dispute_id="disp_pref_t14",
        fact_name="amount_minor",
        status="MISMATCH",
        expected_value="149900",
        observed_value="500000",
        explanation="Amount mismatch detected",
        is_critical=True,
    )
    async_db.add(m)
    await async_db.commit()

    with pytest.raises(StaleDraftException):
        await run_preflight("disp_pref_t14", async_db)


# --- Test 15: Ambiguity Handling ---
@pytest.mark.asyncio
async def test_preflight_ambiguity_warning_handling(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t15")
    await review_contest_draft("disp_pref_t15", ReviewDecision.APPROVE, comment="Approved", db=async_db)

    res = await run_preflight("disp_pref_t15", async_db)
    assert res.status == PreflightStatus.READY


# --- Test 16: Unresolved Conflict Check ---
@pytest.mark.asyncio
async def test_preflight_unresolved_conflict_review_flags(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t16")
    stmt = select(ContestDraftModel).where(ContestDraftModel.dispute_id == "disp_pref_t16")
    db_draft = (await async_db.execute(stmt)).scalars().first()
    flags = dict(db_draft.review_flags or {})
    flags["requires_manual_verification"] = True
    db_draft.review_flags = flags
    await async_db.commit()

    res = await run_preflight("disp_pref_t16", async_db)
    assert len(res.warnings) > 0


# --- Test 17: Approved Draft with Complete Evidence -> READY ---
@pytest.mark.asyncio
async def test_preflight_complete_approved_draft(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t17")
    await review_contest_draft("disp_pref_t17", ReviewDecision.APPROVE, comment="Fully verified", db=async_db)

    res = await run_preflight("disp_pref_t17", async_db)
    assert res.status == PreflightStatus.READY
    assert res.verified_evidence_count == 1
    assert res.verified_financial_identity["amount"] == 149900


# --- Test 18: Incomplete Draft (Missing Factual Arguments) -> BLOCKED ---
@pytest.mark.asyncio
async def test_preflight_incomplete_factual_arguments_returns_blocked(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t18")
    await review_contest_draft("disp_pref_t18", ReviewDecision.APPROVE, comment="Approved", db=async_db)

    stmt = select(ContestDraftModel).where(ContestDraftModel.dispute_id == "disp_pref_t18")
    db_draft = (await async_db.execute(stmt)).scalars().first()
    db_draft.factual_arguments = []  # Empty arguments list
    db_draft.input_fingerprint = compute_contest_draft_input_fingerprint(
        dispute_id="disp_pref_t18",
        payment_id=dispute.payment_id,
        amount=dispute.amount,
        currency=dispute.currency,
        policy_result_id=dispute.policy_results[0].id if dispute.policy_results else None,
        policy_version=dispute.policy_results[0].policy_version if dispute.policy_results else None,
        policy_outcome=dispute.policy_results[0].outcome if dispute.policy_results else None,
        match_results=list(dispute.match_results),
        documents=list(dispute.documents),
    )
    await async_db.commit()

    res = await run_preflight("disp_pref_t18", async_db)
    assert res.status == PreflightStatus.BLOCKED
    assert any("Incomplete factual arguments" in r for r in res.blocking_reasons)


# --- Test 19: Deterministic Repeated Execution ---
@pytest.mark.asyncio
async def test_preflight_deterministic_repeated_execution(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t19")
    await review_contest_draft("disp_pref_t19", ReviewDecision.APPROVE, comment="Approved", db=async_db)

    res1 = await run_preflight("disp_pref_t19", async_db)
    res2 = await run_preflight("disp_pref_t19", async_db)

    assert res1.status == res2.status
    assert res1.input_fingerprint == res2.input_fingerprint
    assert res1.blocking_reasons == res2.blocking_reasons
    assert len(res1.checks) == len(res2.checks)


# --- Test 20: No Source Data Mutation ---
@pytest.mark.asyncio
async def test_preflight_does_not_mutate_source_data(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t20")

    draft_title_before = draft.title
    dispute_status_before = dispute.status

    await run_preflight("disp_pref_t20", async_db)

    stmt = select(ContestDraftModel).where(ContestDraftModel.dispute_id == "disp_pref_t20")
    draft_after = (await async_db.execute(stmt)).scalars().first()

    assert draft_after.title == draft_title_before
    assert dispute.status == dispute_status_before


# --- Test 21: No Financial Field Mutation ---
@pytest.mark.asyncio
async def test_preflight_does_not_mutate_financial_fields(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t21")

    pay_id_before = dispute.payment_id
    amt_before = dispute.amount
    curr_before = dispute.currency

    await run_preflight("disp_pref_t21", async_db)

    assert dispute.payment_id == pay_id_before
    assert dispute.amount == amt_before
    assert dispute.currency == curr_before


# --- Test 22: No Policy Result Mutation ---
@pytest.mark.asyncio
async def test_preflight_does_not_mutate_policy_result(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t22")

    pol_before = dispute.policy_results[0].outcome

    await run_preflight("disp_pref_t22", async_db)

    assert dispute.policy_results[0].outcome == pol_before


# --- Test 23: No AI Calls ---
@pytest.mark.asyncio
async def test_preflight_makes_zero_ai_calls(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t23")

    with patch("backend.app.services.ai_provider.MockAIProvider") as mock_ai:
        res = await run_preflight("disp_pref_t23", async_db)
        mock_ai.assert_not_called()


# --- Test 24: No Razorpay Calls ---
@pytest.mark.asyncio
async def test_preflight_makes_zero_razorpay_calls(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t23")

    with patch("backend.app.services.razorpay_service.RazorpayService") as mock_rzp:
        res = await run_preflight("disp_pref_t23", async_db)
        mock_rzp.assert_not_called()


# --- Test 25: No HTTP Mutation Methods ---
@pytest.mark.asyncio
async def test_preflight_no_http_mutation_methods(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t25")

    with patch("httpx.AsyncClient.post") as mock_post, patch("httpx.AsyncClient.patch") as mock_patch:
        res = await run_preflight("disp_pref_t25", async_db)
        mock_post.assert_not_called()
        mock_patch.assert_not_called()


# --- Test 26: API Contract ---
@pytest.mark.asyncio
async def test_preflight_api_contract(client, async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t26")

    response = await client.post("/api/disputes/disp_pref_t26/contest-submission/preflight")
    assert response.status_code == 200
    data = response.json()
    assert data["dispute_id"] == "disp_pref_t26"
    assert "status" in data
    assert "checks" in data
    assert "verified_financial_identity" in data


# --- Test 27: Request Body Injection Defense ---
@pytest.mark.asyncio
async def test_preflight_api_ignores_client_body_injection(client, async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t27")

    injection_body = {"status": "READY", "review_status": "APPROVED", "amount": 0}
    response = await client.post(
        "/api/disputes/disp_pref_t27/contest-submission/preflight",
        json=injection_body,
    )
    assert response.status_code == 200
    data = response.json()
    # State must be derived from DB (REVIEW_REQUIRED), NOT injected payload
    assert data["status"] == "REVIEW_REQUIRED"


# --- Test 28: Immutable Preflight Snapshot Result ---
@pytest.mark.asyncio
async def test_preflight_immutable_result_persisted(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t28")

    res = await run_preflight("disp_pref_t28", async_db)

    stmt = select(ContestSubmissionPreflight).where(ContestSubmissionPreflight.id == res.id)
    db_rec = (await async_db.execute(stmt)).scalars().first()

    assert db_rec is not None
    assert db_rec.dispute_id == "disp_pref_t28"
    assert db_rec.status == res.status.value


# --- Test 29: Repeated Preflight Idempotency & Snapshots ---
@pytest.mark.asyncio
async def test_preflight_repeated_execution_snapshots(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t29")

    res1 = await run_preflight("disp_pref_t29", async_db)
    res2 = await run_preflight("disp_pref_t29", async_db)

    stmt = select(ContestSubmissionPreflight).where(ContestSubmissionPreflight.dispute_id == "disp_pref_t29")
    snapshots = (await async_db.execute(stmt)).scalars().all()

    assert len(snapshots) == 2
    assert snapshots[0].status == snapshots[1].status


# --- Test 30: Audit / Explainability Verification ---
@pytest.mark.asyncio
async def test_preflight_audit_explainability_detail(async_db):
    dispute, draft = await setup_dispute_for_preflight(async_db, "disp_pref_t30")
    await review_contest_draft("disp_pref_t30", ReviewDecision.APPROVE, comment="Approved", db=async_db)

    res = await run_preflight("disp_pref_t30", async_db)

    codes = [c.check_code for c in res.checks]
    assert "FINANCIAL_IDENTITY_CHECK" in codes
    assert "FINGERPRINT_CHECK" in codes
    assert "POLICY_STATUS_CHECK" in codes
    assert "REVIEW_APPROVAL_CHECK" in codes
    assert "POLICY_CONSISTENCY_CHECK" in codes
    assert "MATCH_CONSISTENCY_CHECK" in codes
    assert "EVIDENCE_PROVENANCE_CHECK" in codes
    assert "FACTUAL_ARGUMENT_CHECK" in codes
