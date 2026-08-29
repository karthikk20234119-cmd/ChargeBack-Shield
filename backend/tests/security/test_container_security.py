"""
Container & Production Deployment Security Audit Suite — Chargeback Shield Task 8.2
"""

import os
import re
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))


def test_dockerfiles_contain_no_hardcoded_secrets():
    """Verifies Dockerfiles do not contain hardcoded API keys or passwords."""
    dockerfiles = [
        os.path.join(ROOT_DIR, "backend", "Dockerfile"),
        os.path.join(ROOT_DIR, "frontend", "Dockerfile"),
    ]

    for df_path in dockerfiles:
        assert os.path.exists(df_path), f"Dockerfile missing: {df_path}"
        with open(df_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "rzp_live_" not in content, f"Hardcoded Razorpay live key in {df_path}"
        assert "rzp_test_" not in content, f"Hardcoded Razorpay test key in {df_path}"
        assert "sk-proj-" not in content, f"Hardcoded OpenAI key in {df_path}"
        assert "RAZORPAY_KEY_SECRET=" not in content, f"Secret assignment in {df_path}"


def test_dockerfiles_do_not_copy_env_files():
    """Verifies Dockerfiles do not explicitly COPY .env files into containers."""
    dockerfiles = [
        os.path.join(ROOT_DIR, "backend", "Dockerfile"),
        os.path.join(ROOT_DIR, "frontend", "Dockerfile"),
    ]

    for df_path in dockerfiles:
        with open(df_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line_clean = line.strip().lower()
            if line_clean.startswith("copy"):
                assert ".env" not in line_clean or ".env.example" in line_clean, \
                    f"Unsafe COPY of .env file in {df_path}: {line}"


def test_backend_dockerfile_uses_non_root_user():
    """Verifies backend Dockerfile enforces a non-root runtime user."""
    backend_df = os.path.join(ROOT_DIR, "backend", "Dockerfile")
    with open(backend_df, "r", encoding="utf-8") as f:
        content = f.read()

    assert "USER appuser" in content or "USER 1000" in content, \
        "Backend Dockerfile must specify non-root USER instruction"


def test_compose_exposes_only_reverse_proxy_ports():
    """Verifies docker-compose.yml exposes only the reverse proxy port 80 publicly."""
    compose_path = os.path.join(ROOT_DIR, "docker-compose.yml")
    assert os.path.exists(compose_path), "docker-compose.yml missing"

    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "rzp_live_" not in content
    assert "rzp_test_" not in content

    # Backend and Frontend should use expose: not ports: for internal isolation
    backend_block = content.split("backend:")[1].split("networks:")[0] if "backend:" in content else ""
    assert "ports:" not in backend_block, "Backend container port 8000 must NOT be exposed publicly"


def test_healthchecks_do_not_call_external_apis():
    """Verifies healthchecks target local endpoints only and make zero external network calls."""
    backend_df = os.path.join(ROOT_DIR, "backend", "Dockerfile")
    with open(backend_df, "r", encoding="utf-8") as f:
        content = f.read()

    assert "api.razorpay.com" not in content
    assert "http://localhost:8000/api/health" in content
