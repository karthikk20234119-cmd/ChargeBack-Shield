import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.observability import metrics_collector

logger = logging.getLogger(__name__)

SAFE_REQUEST_ID_REGEX = r"^[a-zA-Z0-9\-_]{8,64}$"


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns or validates a cryptographically secure X-Request-ID
    correlation token to every HTTP request, tracks performance metrics,
    and attaches security response headers.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        incoming_id = request.headers.get("X-Request-ID")

        # Validate incoming request ID format to prevent injection/oversized headers
        clean_id = incoming_id.replace("-", "").replace("_", "") if incoming_id else ""
        if incoming_id and len(incoming_id) <= 64 and clean_id.isalnum():
            request_id = incoming_id
        else:
            request_id = str(uuid.uuid4())

        # Store in request state for logging context
        request.state.request_id = request_id

        # Process request
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Record metrics safely
            metrics_collector.record_request(duration_ms=duration_ms, status_code=response.status_code)

            # Propagate correlation ID & timing to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

            # Attach production security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            metrics_collector.record_request(duration_ms=duration_ms, status_code=500, category="INTERNAL_ERROR")
            raise exc
