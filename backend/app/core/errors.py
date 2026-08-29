"""
Centralized Production Error & Exception Handling — Chargeback Shield Task 8.1
"""

import logging
import traceback
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.config import settings

logger = logging.getLogger(__name__)


def setup_error_handlers(app: FastAPI) -> None:
    """Configures centralized, production-safe exception handlers."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Request validation failed", "errors": exc.errors(), "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")

        # Log full traceback server-side only
        logger.error(
            f"Unhandled exception on route {request.url.path} (request_id={request_id}): {exc}\n"
            f"{traceback.format_exc()}"
        )

        # In production or non-debug mode, return safe error payload without exposing tracebacks or secrets
        if not settings.is_debug():
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error", "request_id": request_id},
                headers={"X-Request-ID": request_id},
            )

        # Development debug response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )
