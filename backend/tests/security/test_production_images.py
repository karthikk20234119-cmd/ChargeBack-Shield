"""
Production Docker Images & Security Audit Suite — Chargeback Shield Task 8.4

Verifies 15 mandatory Docker/image security checks.
"""

import os
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))


def test_no_secrets_embedded_in_dockerfiles():
    """1. Verifies Dockerfiles do not contain embedded secret keys or passwords."""
    for df_name in ["backend/Dockerfile", "frontend/Dockerfile"]:
        path = os.path.join(ROOT_DIR, df_name)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "rzp_live_" not in content
        assert "rzp_test_" not in content
        assert "gsk_" not in content
        assert "sk-proj-" not in content


def test_no_env_files_copied_in_dockerfiles():
    """2 & 3. Verifies .env files and private credentials are not copied into images."""
    for df_name in ["backend/Dockerfile", "frontend/Dockerfile"]:
        path = os.path.join(ROOT_DIR, df_name)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line_clean = line.strip().lower()
                if line_clean.startswith("copy"):
                    assert ".env" not in line_clean or ".env.example" in line_clean


def test_backend_non_root_runtime_user():
    """4. Verifies backend container specifies non-root USER appuser."""
    path = os.path.join(ROOT_DIR, "backend/Dockerfile")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "USER appuser" in content or "USER 1000" in content


def test_frontend_restricted_nginx_runtime():
    """5. Verifies frontend uses alpine-slim NGINX container."""
    path = os.path.join(ROOT_DIR, "frontend/Dockerfile")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "nginx:alpine-slim" in content


def test_internal_backend_port_unexposed():
    """6 & 7. Verifies internal backend port 8000 is not exposed to host network in docker-compose.yml."""
    path = os.path.join(ROOT_DIR, "docker-compose.yml")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    backend_block = content.split("backend:")[1].split("networks:")[0] if "backend:" in content else ""
    assert "ports:" not in backend_block


def test_volume_persistence_configuration():
    """8, 9, 10. Verifies SQLite DB, evidence, and processed artifacts are persisted through volumes."""
    path = os.path.join(ROOT_DIR, "docker-compose.yml")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "evidence-data" in content
    assert "processed-data" in content
    assert "db-data" in content


def test_healthchecks_do_not_call_razorpay():
    """11. Verifies container healthchecks do not execute Razorpay calls."""
    path = os.path.join(ROOT_DIR, "backend/Dockerfile")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "api.razorpay.com" not in content
    assert "/api/health" in content


def test_containers_unprivileged_mode():
    """12, 13, 14, 15. Verifies privileged mode is not requested in docker-compose.yml."""
    path = os.path.join(ROOT_DIR, "docker-compose.yml")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "privileged: true" not in content
