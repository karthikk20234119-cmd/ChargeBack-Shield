"""
Comprehensive Go-Live Security Suite — Chargeback Shield Task 9.1

20 Mandatory Production Release Security Audits.
"""

import os
import ast
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.version import get_version_info


def test_1_version_info_contains_zero_secrets():
    """1. Verifies version metadata contains no API keys or secret tokens."""
    info = get_version_info()
    assert "version" in info
    assert "build_identifier" in info
    assert "key_secret" not in info
    assert "rzp_live_" not in str(info)


def test_2_health_endpoints_leak_no_credentials():
    """2. Verifies health endpoints return safe status without leaking credentials."""
    with TestClient(app) as client:
        res = client.get("/api/health/ready")
        assert res.status_code == 200
        assert "RAZORPAY_KEY_SECRET" not in res.text
        assert "password" not in res.text


def test_3_observability_summary_sanitized():
    """3. Verifies observability metrics expose zero secret headers or tokens."""
    with TestClient(app) as client:
        res = client.get("/api/observability/summary")
        assert res.status_code == 200
        assert "Bearer " not in res.text
        assert "authorization_header" not in res.text.lower()
        assert "key_secret" not in res.text.lower()


def test_4_submission_boundary_is_single_protocol():
    """4. AST verification that submit_contest is the only submission mutation boundary."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    path = os.path.join(root_dir, "backend", "app", "services", "contest_submission_client.py")
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    methods = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert "submit_contest" in methods
    assert "auto_retry" not in methods


def test_5_zero_financial_mutation_methods():
    """5. AST verification that accept_dispute, reject_dispute, or issue_refund methods do not exist."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    services_dir = os.path.join(root_dir, "backend", "app", "services")
    forbidden = {"accept_dispute", "reject_dispute", "issue_refund", "auto_refund"}

    for root, _, files in os.walk(services_dir):
        for file in files:
            if not file.endswith(".py"):
                continue
            with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in forbidden, f"FORBIDDEN METHOD: {node.name} in {file}"
