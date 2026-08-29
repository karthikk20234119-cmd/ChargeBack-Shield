"""
Deployment Smoke Test Suite — Chargeback Shield Task 8.2
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


def test_health_endpoint_smoke():
    """Verifies health check endpoint responds with 200 OK and safe status payload."""
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Chargeback Shield API"
    assert "rzp_live_" not in response.text
    assert "X-Request-ID" in response.headers


def test_cors_headers_smoke():
    """Verifies CORS security headers in response."""
    client = TestClient(app)
    response = client.get("/api/health", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_evidence_storage_path_accessible():
    """Verifies evidence storage directories are initialized and accessible."""
    from backend.app.config import settings
    import os

    assert os.path.exists(settings.UPLOAD_DIR), "Evidence upload directory must exist"
    assert os.path.exists(settings.PROCESSED_DIR), "Processed storage directory must exist"
