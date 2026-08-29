"""
Production Configuration & Security Isolation Test Suite — Chargeback Shield Task 8.1
"""

import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.core.middleware import RequestCorrelationMiddleware
from backend.app.core.errors import setup_error_handlers
from backend.app.core.logging import redact_secrets
from backend.app.core.startup import validate_production_startup


def test_production_debug_disabled():
    """Verifies that production environment forces DEBUG to False."""
    original_app_env = settings.APP_ENV
    original_debug = settings.DEBUG
    try:
        settings.APP_ENV = "production"
        settings.DEBUG = True
        assert settings.is_debug() is False, "Production mode must force is_debug() to False"
    finally:
        settings.APP_ENV = original_app_env
        settings.DEBUG = original_debug


def test_cors_origins_parsing():
    """Verifies CORS allowed origins parsing."""
    origins = settings.get_cors_origins()
    assert isinstance(origins, list)
    assert len(origins) > 0


def test_secret_redaction_utility():
    """Verifies static text secret redaction functions."""
    raw_log = "Error accessing rzp_live_9988776655 with secret rzp_test_secret123 and sk-proj-openaisamplekey"
    redacted = redact_secrets(raw_log)
    assert "rzp_live_9988776655" not in redacted
    assert "rzp_test_secret123" not in redacted
    assert "sk-proj-openaisamplekey" not in redacted
    assert "[REDACTED_RAZORPAY_KEY]" in redacted
    assert "[REDACTED_OPENAI_KEY]" in redacted


def test_request_correlation_middleware():
    """Verifies X-Request-ID correlation header generation and propagation."""
    test_app = FastAPI()
    test_app.add_middleware(RequestCorrelationMiddleware)

    @test_app.get("/test")
    async def sample_endpoint():
        return {"status": "ok"}

    client = TestClient(test_app)

    # Test generated request ID
    response = client.get("/test")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    generated_id = response.headers["X-Request-ID"]
    assert len(generated_id) > 10

    # Test propagating safe incoming request ID
    custom_id = "custom-req-id-12345"
    response_custom = client.get("/test", headers={"X-Request-ID": custom_id})
    assert response_custom.headers["X-Request-ID"] == custom_id


def test_production_error_sanitization():
    """Verifies unhandled 500 errors conceal tracebacks and DB strings in production mode."""
    original_app_env = settings.APP_ENV
    original_debug = settings.DEBUG

    try:
        settings.APP_ENV = "production"
        settings.DEBUG = False

        test_app = FastAPI()
        test_app.add_middleware(RequestCorrelationMiddleware)
        setup_error_handlers(test_app)

        @test_app.get("/error")
        async def exception_endpoint():
            raise ValueError("Sensitive DB Connection String sqlite:///secret_pass@localhost/db")

        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/error")

        assert response.status_code == 500
        body = response.json()
        assert body["detail"] == "Internal server error"
        assert "secret_pass" not in response.text
        assert "Traceback" not in response.text
        assert "request_id" in body
    finally:
        settings.APP_ENV = original_app_env
        settings.DEBUG = original_debug


def test_startup_validator_rejects_wildcard_cors_in_production():
    """Verifies production startup fails if CORS contains wildcard '*'."""
    original_app_env = settings.APP_ENV
    original_origins = settings.CORS_ALLOWED_ORIGINS
    original_debug = settings.DEBUG

    try:
        settings.APP_ENV = "production"
        settings.DEBUG = False
        settings.CORS_ALLOWED_ORIGINS = ["*"]

        with pytest.raises(RuntimeError) as exc_info:
            validate_production_startup()

        assert "CORS_ALLOWED_ORIGINS cannot contain wildcard '*'" in str(exc_info.value)
    finally:
        settings.APP_ENV = original_app_env
        settings.CORS_ALLOWED_ORIGINS = original_origins
        settings.DEBUG = original_debug


def test_no_hardcoded_secrets_in_settings_defaults():
    """Verifies Settings default values do not contain live hardcoded credentials."""
    assert "rzp_live_" not in settings.RAZORPAY_KEY_ID
    assert "rzp_live_" not in settings.RAZORPAY_KEY_SECRET
    assert "sk-live-" not in settings.OPENAI_API_KEY
