"""
Local Production Startup Configuration Validator — Chargeback Shield Task 8.1
"""

import os
import logging
from backend.app.config import settings

logger = logging.getLogger(__name__)


def validate_production_startup() -> None:
    """
    Validates environment settings locally on startup without executing external HTTP requests.
    Raises RuntimeError if production environment contains invalid or unsafe configurations.
    """
    if not settings.is_production():
        logger.info(f"Startup validation complete. Environment: {settings.APP_ENV} (Development/Testing)")
        return

    logger.info("Performing local production configuration startup validation...")

    # 1. Debug Invariant
    if settings.DEBUG:
        raise RuntimeError("PRODUCTION SECURITY FAILURE: DEBUG mode must be False in production environment")

    # 2. Database URL Invariant
    if not settings.DATABASE_URL or settings.DATABASE_URL.strip() == "":
        raise RuntimeError("PRODUCTION SECURITY FAILURE: DATABASE_URL must be explicitly configured")

    # 3. CORS Invariant
    cors_origins = settings.get_cors_origins()
    if "*" in cors_origins:
        raise RuntimeError("PRODUCTION SECURITY FAILURE: CORS_ALLOWED_ORIGINS cannot contain wildcard '*' in production")

    # 4. Storage Directories Writability
    for directory in [settings.UPLOAD_DIR, settings.PROCESSED_DIR]:
        os.makedirs(directory, exist_ok=True)
        if not os.access(directory, os.W_OK):
            raise RuntimeError(f"PRODUCTION STARTUP FAILURE: Directory '{directory}' is not writable")

    logger.info("Local production configuration validation passed successfully.")
