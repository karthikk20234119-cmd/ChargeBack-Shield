"""
Observability End-to-End Integration Suite — Chargeback Shield Task 8.3
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.observability import metrics_collector


def test_e2e_observability_pipeline_tracking():
    """Simulates lifecycle HTTP requests and verifies metrics aggregation and summary outputs."""
    client = TestClient(app)

    # 1. Hit health endpoints
    res_live = client.get("/api/health/live")
    assert res_live.status_code == 200

    res_ready = client.get("/api/health/ready")
    assert res_ready.status_code == 200

    # 2. Trigger pipeline increments
    metrics_collector.increment("evidence_processing_count", 1)
    metrics_collector.increment("extraction_count", 1)
    metrics_collector.increment("matching_count", 1)
    metrics_collector.increment("policy_evaluation_count", 1)
    metrics_collector.increment("draft_generation_count", 1)
    metrics_collector.increment("review_approval_count", 1)
    metrics_collector.increment("preflight_ready_count", 1)
    metrics_collector.increment("submission_success_count", 1)

    # 3. Retrieve metrics snapshot
    res_metrics = client.get("/api/observability/metrics")
    assert res_metrics.status_code == 200
    metrics_data = res_metrics.json()
    assert metrics_data["evidence_processing"]["total"] >= 1
    assert metrics_data["policy_matching"]["reviews_approved"] >= 1

    # 4. Retrieve summary
    res_summary = client.get("/api/observability/summary")
    assert res_summary.status_code == 200
    summary_data = res_summary.json()
    assert summary_data["status"] in ["HEALTHY", "DEGRADED"]
    assert "dependencies" in summary_data
