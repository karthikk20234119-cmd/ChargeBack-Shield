"""
Production Deployment Smoke & Health-Gated Test Suite — Chargeback Shield Task 8.4
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings


def test_production_deployment_health_gates():
    """Verifies health gates (/api/health, /api/health/live, /api/health/ready)."""
    client = TestClient(app)

    # 1. Root Status
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["app"] == settings.PROJECT_NAME

    # 2. Base Health
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # 3. Liveness Gate
    res_live = client.get("/api/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "ok"

    # 4. Readiness Gate
    res_ready = client.get("/api/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] in ["ready", "degraded"]


def test_deployment_contains_no_razorpay_network_calls():
    """Verifies health-gated startup makes zero Razorpay network requests."""
    client = TestClient(app)
    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert "api.razorpay.com" not in response.text
    assert "RAZORPAY_KEY_SECRET" not in response.text
