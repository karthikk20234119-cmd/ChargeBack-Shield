"""
Observability Unit Test Suite — Chargeback Shield Task 8.3
"""

import pytest
from backend.app.core.observability import (
    MetricsCollector,
    classify_error,
    ErrorCategory,
    check_storage_health,
    log_observability_event,
)


def test_metrics_collector_recording():
    """Verifies MetricsCollector records requests, latencies, and status error codes correctly."""
    collector = MetricsCollector()

    collector.record_request(duration_ms=50.0, status_code=200)
    collector.record_request(duration_ms=150.0, status_code=500, category=ErrorCategory.INTERNAL_ERROR)

    snapshot = collector.get_metrics_snapshot()
    assert snapshot["request_count"] == 2
    assert snapshot["request_error_count"] == 1
    assert snapshot["error_rate_pct"] == 50.0
    assert snapshot["average_latency_ms"] == 100.0
    assert snapshot["errors_by_category"][ErrorCategory.INTERNAL_ERROR] == 1


def test_error_classification():
    """Verifies deterministic error classification mapping."""
    assert classify_error(ValueError("Invalid payload")) == ErrorCategory.VALIDATION_ERROR
    assert classify_error(PermissionError("Access denied")) == ErrorCategory.AUTHORIZATION_ERROR
    assert classify_error(TimeoutError("Connection timed out")) == ErrorCategory.TIMEOUT
    assert classify_error(RuntimeError("General failure")) == ErrorCategory.INTERNAL_ERROR


def test_storage_health_checker():
    """Verifies local storage health checker."""
    health = check_storage_health()
    assert health["status"] in ["HEALTHY", "DEGRADED", "UNAVAILABLE"]
    assert "details" in health


def test_log_observability_event():
    """Verifies log_observability_event executes cleanly without throwing exceptions."""
    log_observability_event(
        event_type="SUBMISSION_COMPLETED",
        stage="SUBMISSION",
        dispute_id="disp_test123",
        details={"status": "SUBMITTED"}
    )
