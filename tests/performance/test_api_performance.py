"""
API Response Latency Benchmark Suite — Chargeback Shield Task 8.5

Measures min, avg, P50, P95, P99, max latency for read-only endpoints across
Health, Dashboard, Analytics, Audit, and Operations modules.
"""

import time
import math
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


def measure_endpoint_latencies(client: TestClient, endpoint: str, num_requests: int = 50) -> dict:
    """Helper to benchmark an endpoint and calculate P50, P95, P99 latency percentiles."""
    latencies = []
    for _ in range(num_requests):
        t0 = time.perf_counter()
        response = client.get(endpoint)
        t1 = time.perf_counter()
        assert response.status_code == 200, f"Endpoint {endpoint} returned status {response.status_code}"
        latencies.append((t1 - t0) * 1000.0)  # ms

    latencies.sort()
    n = len(latencies)

    def percentile(p: float) -> float:
        k = (n - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return latencies[int(k)]
        d0 = latencies[int(f)] * (c - k)
        d1 = latencies[int(c)] * (k - f)
        return d0 + d1

    return {
        "min_ms": float(latencies[0]),
        "avg_ms": float(sum(latencies) / n),
        "p50_ms": float(percentile(50.0)),
        "p95_ms": float(percentile(95.0)),
        "p99_ms": float(percentile(99.0)),
        "max_ms": float(latencies[-1]),
    }


def test_health_endpoints_performance():
    """Benchmarks Health endpoints latency."""
    with TestClient(app) as client:
        for path in ["/api/health", "/api/health/live", "/api/health/ready"]:
            stats = measure_endpoint_latencies(client, path, num_requests=30)
            assert stats["p95_ms"] < 200.0, f"Health endpoint {path} P95 exceeds 200ms: {stats['p95_ms']:.2f}ms"


def test_dashboard_endpoints_performance():
    """Benchmarks Dashboard endpoints latency."""
    with TestClient(app) as client:
        for path in ["/api/dashboard/summary", "/api/dashboard/disputes", "/api/dashboard/alerts"]:
            stats = measure_endpoint_latencies(client, path, num_requests=20)
            assert stats["p95_ms"] < 500.0, f"Dashboard endpoint {path} P95 exceeds 500ms: {stats['p95_ms']:.2f}ms"


def test_analytics_endpoints_performance():
    """Benchmarks Analytics endpoints latency."""
    with TestClient(app) as client:
        for path in ["/api/analytics/summary", "/api/analytics/outcomes", "/api/analytics/funnel"]:
            stats = measure_endpoint_latencies(client, path, num_requests=20)
            assert stats["p95_ms"] < 500.0, f"Analytics endpoint {path} P95 exceeds 500ms: {stats['p95_ms']:.2f}ms"


def test_operations_endpoints_performance():
    """Benchmarks Operations & SLA endpoints latency."""
    with TestClient(app) as client:
        for path in ["/api/operations/alerts", "/api/operations/sla", "/api/operations/health"]:
            stats = measure_endpoint_latencies(client, path, num_requests=20)
            assert stats["p95_ms"] < 500.0, f"Operations endpoint {path} P95 exceeds 500ms: {stats['p95_ms']:.2f}ms"
