"""
Release Metadata Module — Chargeback Shield Task 9.1

Provides deterministic version, build, and release identification information for production deployment.
Contains ZERO secrets, API keys, credentials, or environment sensitive details.
"""

import os
from typing import Dict, Any

APPLICATION_NAME = "Chargeback Shield"
VERSION = "1.0.0"
RELEASE_TAG = "production-v1.0.0"
BUILD_IDENTIFIER = "2026-08-29.v1.0.0"
BUILD_TIMESTAMP_UTC = "2026-08-29T20:00:00Z"


def get_version_info() -> Dict[str, Any]:
    """Returns deterministic application version and build metadata."""
    return {
        "application_name": APPLICATION_NAME,
        "version": VERSION,
        "release_tag": RELEASE_TAG,
        "build_identifier": BUILD_IDENTIFIER,
        "build_timestamp_utc": BUILD_TIMESTAMP_UTC,
        "environment": os.getenv("APP_ENV", "production"),
    }
