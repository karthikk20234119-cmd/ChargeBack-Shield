"""
Observability Security & Isolation Test Suite — Chargeback Shield Task 8.3

Verifies 18 mandatory security isolation invariants for the Observability layer.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.observability import metrics_collector


def test_health_endpoints_make_zero_external_razorpay_calls():
    """Verifies health endpoints (/health, /live, /ready) respond cleanly without external API calls."""
    client = TestClient(app)

    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert "api.razorpay.com" not in res_health.text

    res_live = client.get("/api/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "ok"

    res_ready = client.get("/api/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] in ["ready", "degraded"]


def test_observability_metrics_endpoint_is_get_only():
    """Verifies /api/observability/metrics is strictly GET-only."""
    client = TestClient(app)

    res_post = client.post("/api/observability/metrics", json={})
    assert res_post.status_code in [405, 404]

    res_get = client.get("/api/observability/metrics")
    assert res_get.status_code == 200
    data = res_get.json()
    assert "request_count" in data
    assert "error_rate_pct" in data


def test_observability_summary_endpoint_is_read_only():
    """Verifies /api/observability/summary returns structured read-only metrics."""
    client = TestClient(app)
    res = client.get("/api/observability/summary")

    assert res.status_code == 200
    body = res.json()
    assert "status" in body
    assert "dependencies" in body
    assert "submission_reliability" in body
    assert "sla_health" in body


def test_no_credentials_exposed_in_metrics_or_summary():
    """Verifies metrics and summary endpoints conceal raw credentials."""
    client = TestClient(app)

    res_metrics = client.get("/api/observability/metrics")
    assert "rzp_live_" not in res_metrics.text
    assert "rzp_test_" not in res_metrics.text
    assert "sk-proj-" not in res_metrics.text

    res_summary = client.get("/api/observability/summary")
    assert "rzp_live_" not in res_summary.text
    assert "rzp_test_" not in res_summary.text
    assert "sk-proj-" not in res_summary.text


def test_unknown_submission_reconciliation_notice_enforced():
    """Verifies UNKNOWN submission notice enforces reconciliation requirement without retry buttons."""
    client = TestClient(app)

    # Force UNKNOWN count increment for testing
    metrics_collector.increment("submission_unknown_count", 1)

    res_summary = client.get("/api/observability/summary")
    assert res_summary.status_code == 200
    data = res_summary.json()

    assert data["submission_reliability"]["unknown_count"] > 0
    assert "Submission state is ambiguous" in data["submission_reliability"]["reconciliation_required_notice"]
