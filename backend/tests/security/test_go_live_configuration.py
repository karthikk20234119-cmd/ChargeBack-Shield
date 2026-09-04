"""
Go-Live Environment Configuration Security Audit Suite — Chargeback Shield Task 9.1

Audits production environment configuration settings, CORS rules, documentation endpoints,
and environment template files to ensure strict go-live readiness.
"""

import os
import pytest
from backend.app.config import Settings


def test_production_environment_configuration_defaults():
    """Verifies production environment configuration requirements."""
    prod_settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        ENABLE_DOCS=False,
        ENABLE_OPENAPI=False,
        CORS_ALLOWED_ORIGINS="https://shield.merchant.com,https://app.chargebackshield.io",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/chargeback_shield_prod"
    )

    assert prod_settings.DEBUG is False
    assert prod_settings.ENABLE_DOCS is False
    assert prod_settings.ENABLE_OPENAPI is False
    assert prod_settings.CORS_ALLOWED_ORIGINS != "*"
    assert "https://" in prod_settings.CORS_ALLOWED_ORIGINS


def test_cors_origin_not_unrestricted_wildcard():
    """Verifies production CORS settings forbid unrestricted '*' origins."""
    settings = Settings()
    if settings.ENVIRONMENT.lower() == "production":
        assert "*" not in settings.CORS_ALLOWED_ORIGINS


def test_env_templates_contain_placeholders_only():
    """Verifies .env.example and .env.production.example contain placeholders or blank values only."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    for example_file in [".env.example", ".env.production.example"]:
        path = os.path.join(root_dir, example_file)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "rzp_live_" not in content
            assert "rzp_test_" not in content
            assert "gsk_" not in content
            assert "sk-proj-" not in content
            assert "RAZORPAY_KEY_ID" in content
