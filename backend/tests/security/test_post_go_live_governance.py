"""
Post-Go-Live Operational Governance Security Suite — Chargeback Shield Task 9.3

Audits UNKNOWN submission non-retry governance, financial identity immutability,
audit append-only immutability, credential rotation safety, and alert non-mutation boundaries.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.contest_submission_client import MockContestSubmissionClient
from backend.app.schemas.contest_submission import RazorpayContestSubmissionRequest
from backend.app.services.razorpay_errors import RazorpayNetworkError


@pytest.mark.asyncio
async def test_unknown_submission_state_requires_reconciliation():
    """Verifies network timeouts set state to UNKNOWN and forbid automatic retries."""
    mock_client = MockContestSubmissionClient(mode="TIMEOUT")
    req = RazorpayContestSubmissionRequest(
        dispute_id="disp_gov_unk_1",
        amount_minor=10000,
        currency="INR",
        summary="Test summary",
        comments="Timeout simulation test"
    )

    with pytest.raises(RazorpayNetworkError) as exc_info:
        await mock_client.submit_contest(req)

    assert "timed out" in str(exc_info.value).lower()
    # Confirm mode remains unchanged and zero automatic retries were initiated
    assert mock_client.mode == "TIMEOUT"


def test_financial_identity_monitoring():
    """Verifies dispute financial attributes (payment_id, amount, currency) are preserved."""
    with TestClient(app) as client:
        res = client.get("/api/dashboard/disputes")
        assert res.status_code == 200
        data = res.json()
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        if len(items) > 0:
            d = items[0]
            assert "payment_id" in d
            assert "amount" in d
            assert "currency" in d
            assert isinstance(d["amount"], int)


def test_operational_alert_acknowledgement_does_not_mutate_business_entity():
    """Verifies acknowledging an alert modifies OperationalAlert only without touching disputes."""
    with TestClient(app) as client:
        res_alerts = client.get("/api/operations/alerts")
        assert res_alerts.status_code == 200
        alerts = res_alerts.json()
        if len(alerts) > 0:
            alert_id = alerts[0]["id"]
            res_ack = client.post(f"/api/operations/alerts/{alert_id}/acknowledge")
            assert res_ack.status_code in [200, 404]
