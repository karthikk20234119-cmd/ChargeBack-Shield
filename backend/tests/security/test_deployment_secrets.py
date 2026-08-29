"""
Static Deployment Secret Audit Suite — Chargeback Shield Task 8.4

Scans repository deployment files for forbidden live key patterns or committed credentials.
"""

import os
import re
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))

LIVE_SECRET_PATTERNS = [
    re.compile(r"rzp_live_[a-zA-Z0-9]{10,}"),
    re.compile(r"sk-live-[a-zA-Z0-9]{10,}"),
]

# Paths allowed to contain synthetic test assertions in security test suites
ALLOWLISTED_TEST_FILES = [
    "backend/tests/security/test_configuration_security.py",
    "backend/tests/security/test_final_security_audit.py",
    "frontend/tests/security/review-workspace-security.test.ts",
    "frontend/tests/security/operations-security.test.ts",
    "frontend/tests/security/analytics-security.test.ts",
]


def test_repository_static_secret_scan():
    """Scans application code, config templates, and deployment files for live key patterns."""
    scanned_files = 0

    for root, dirs, files in os.walk(ROOT_DIR):
        # Exclude git, node_modules, venv, and backup folders
        dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "venv", ".venv", "backups", "dist", "storage"]]

        for file in files:
            if not file.endswith((".py", ".ts", ".tsx", ".js", ".json", ".yml", ".yaml", ".env", ".example", "Dockerfile")):
                continue

            rel_path = os.path.relpath(os.path.join(root, file), ROOT_DIR).replace("\\", "/")
            if rel_path in ALLOWLISTED_TEST_FILES:
                continue

            full_path = os.path.join(root, file)
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            for pattern in LIVE_SECRET_PATTERNS:
                matches = pattern.findall(content)
                assert len(matches) == 0, f"SECURITY VIOLATION: Live secret pattern match in {rel_path}: {matches}"

            scanned_files += 1

    assert scanned_files > 20, "Static secret scan must inspect at least 20 source files"
