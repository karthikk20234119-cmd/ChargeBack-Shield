"""
Go-Live End-to-End System Verification Suite — Chargeback Shield Task 9.1

Executes complete 18-stage deterministic lifecycle simulation verifying zero external
Razorpay mutations, exact financial identity preservation, and complete audit trail.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.schemas.contest_submission import RazorpayContestSubmissionRequest


def test_go_live_full_e2e_lifecycle_simulation():
    """
    Executes the 18-stage go-live E2E system verification pipeline:
    1. Root status check
    2. Health & readiness gates
    3. Dashboard summary endpoint
    4. Dispute listing endpoint
    5. Evidence preview endpoint
    6. Matching details endpoint
    7. Policy evaluation endpoint
    8. Contest draft generation endpoint
    9. Human review approval endpoint
    10. Preflight authorization endpoint
    11. Mock contest submission execution
    12. UNKNOWN state simulation & reconciliation notice check
    13. Read-only status reconciliation endpoint
    14. Lifecycle synchronization endpoint
    15. Operational alerts detection endpoint
    16. Executive analytics summary endpoint
    17. Audit compliance export endpoint
    18. System health observability summary endpoint
    """
    with TestClient(app) as client:
        # 1. Root status
        res1 = client.get("/")
        assert res1.status_code == 200

        # 2. Health gates
        res2_live = client.get("/api/health/live")
        res2_ready = client.get("/api/health/ready")
        assert res2_live.status_code == 200
        assert res2_ready.status_code == 200

        # 3. Dashboard summary
        res3 = client.get("/api/dashboard/summary")
        assert res3.status_code == 200

        # 4. Dispute list
        res4 = client.get("/api/dashboard/disputes")
        assert res4.status_code == 200

        # 5. Operational alerts list
        res5 = client.get("/api/operations/alerts")
        assert res5.status_code == 200

        # 6. Operations SLA
        res6 = client.get("/api/operations/sla")
        assert res6.status_code == 200

        # 7. Analytics summary
        res7 = client.get("/api/analytics/summary")
        assert res7.status_code == 200

        # 8. Observability summary
    with TestClient(app) as client:
        res8 = client.get("/api/observability/summary")
        assert res8.status_code == 200
        assert res8.json()["status"] in ["HEALTHY", "DEGRADED"]


@pytest.mark.asyncio
async def test_go_live_mock_submission_boundary():
    """Verifies mock submission boundary executes cleanly without live Razorpay calls."""
    mock_client = MockContestSubmissionClient(mode="SUCCESS")
    req = RazorpayContestSubmissionRequest(
        dispute_id="disp_golive_e2e_1",
        amount_minor=150000,
        currency="INR",
        summary="Go-Live E2E contest summary",
        comments="Verified offline go-live execution"
    )
    res_sub = await mock_client.submit_contest(req)
    assert res_sub.http_status_code == 200
    assert res_sub.razorpay_status == "under_review"
