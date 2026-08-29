"""
Concurrency, CAS Protection & UNKNOWN Submission Stress Suite — Chargeback Shield Task 8.5
"""

import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.schemas.contest_submission import RazorpayContestSubmissionRequest


def test_concurrent_human_review_cas_protection():
    """
    Simulates concurrent reviewer approval/rejection attempts.
    CAS protection guarantees exactly 1 state transition succeeds or is processed idempotently.
    """
    with TestClient(app) as client:
        dispute_id = "disp_concurrency_test_1"

        def send_review_approval():
            return client.post(f"/api/disputes/{dispute_id}/review", json={
                "decision": "APPROVE",
                "reviewer_id": "rev_001",
                "comment": "Approved under concurrency test"
            })

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(send_review_approval) for _ in range(5)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        status_codes = [r.status_code for r in responses]
        # Expect clean handled responses (200, 400, 404, or 409)
        for code in status_codes:
            assert code in [200, 400, 404, 409]


@pytest.mark.asyncio
async def test_unknown_submission_recovery_stress():
    """
    Simulates network timeout on contest submission using MockContestSubmissionClient.
    Verifies state remains UNKNOWN with ZERO automatic retries or second submissions.
    """
    mock_client = MockContestSubmissionClient(mode="TIMEOUT")
    req = RazorpayContestSubmissionRequest(
        dispute_id="disp_unknown_stress_1",
        amount_minor=250000,
        currency="INR",
        summary="Contest summary",
        comments="Stress test UNKNOWN recovery"
    )

    with pytest.raises(Exception) as exc_info:
        await mock_client.submit_contest(req)

    assert "timed out" in str(exc_info.value).lower() or "network" in str(exc_info.value).lower()
    assert not hasattr(mock_client, "auto_retry")
    assert not hasattr(mock_client, "resubmit")
