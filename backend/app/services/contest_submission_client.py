"""
Dedicated Contest Submission Client Abstraction — Chargeback Shield Task 5.4B

Defines a dedicated Protocol and client implementations (HttpContestSubmissionClient and MockContestSubmissionClient)
exposing ONLY the explicitly authorized contest submission operation.

FINANCIAL & ARCHITECTURAL SAFETY:
- Exposes ONLY `submit_contest()`.
- Generic HTTP methods (request, mutate, post, patch, put, delete) are STRICTLY FORBIDDEN.
- Hard-codes approved Razorpay contest endpoint.
- Preserves read-only status of existing RazorpayClient.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Protocol, runtime_checkable

import httpx

from backend.app.config import Settings
from backend.app.schemas.contest_submission import (
    RazorpayContestSubmissionRequest,
    RazorpayContestSubmissionResponse,
)
from backend.app.services.razorpay_errors import (
    RazorpayAuthenticationError,
    RazorpayClientError,
    RazorpayNetworkError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
    RazorpayServerError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol Interface
# ---------------------------------------------------------------------------


@runtime_checkable
class ContestSubmissionClient(Protocol):
    """
    Dedicated submission client protocol exposing ONLY contest submission.
    No generic HTTP or mutation methods exist.
    """

    async def submit_contest(
        self, request: RazorpayContestSubmissionRequest
    ) -> RazorpayContestSubmissionResponse: ...


# ---------------------------------------------------------------------------
# Production HTTP Client Implementation
# ---------------------------------------------------------------------------


class HttpContestSubmissionClient:
    """
    Production HTTP implementation of ContestSubmissionClient using httpx.
    Hard-codes the approved Razorpay contest submission URL structure.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    async def submit_contest(
        self, request: RazorpayContestSubmissionRequest
    ) -> RazorpayContestSubmissionResponse:
        url = f"{self.settings.RAZORPAY_API_BASE_URL.rstrip('/')}/v1/disputes/{request.dispute_id}/contest"
        auth = (self.settings.RAZORPAY_KEY_ID, self.settings.RAZORPAY_KEY_SECRET)

        payload = {
            "amount": request.amount_minor,
            "currency": request.currency,
            "summary": request.summary,
        }
        if request.comments:
            payload["comments"] = request.comments
        if request.documents:
            payload["documents"] = request.documents
        if request.evidence:
            payload["evidence"] = request.evidence

        logger.info(
            "AUDIT [Contest Submission Request Initiated]: dispute_id=%s, amount=%d, currency=%s, doc_count=%d",
            request.dispute_id,
            request.amount_minor,
            request.currency,
            len(request.documents),
        )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, auth=auth)
        except httpx.TimeoutException as exc:
            logger.error("AUDIT [Contest Submission Timeout]: dispute_id=%s, error=%s", request.dispute_id, str(exc))
            raise RazorpayNetworkError(message=f"Request to Razorpay timed out: {exc}", dispute_id=request.dispute_id) from exc
        except httpx.RequestError as exc:
            logger.error("AUDIT [Contest Submission Network Error]: dispute_id=%s, error=%s", request.dispute_id, str(exc))
            raise RazorpayNetworkError(message=f"Network error connecting to Razorpay: {exc}", dispute_id=request.dispute_id) from exc

        status_code = resp.status_code

        if status_code in (200, 201, 202):
            try:
                data = resp.json()
            except Exception as exc:
                data = {"raw": resp.text}

            logger.info(
                "AUDIT [Contest Submission HTTP Success]: dispute_id=%s, status_code=%d",
                request.dispute_id,
                status_code,
            )
            return RazorpayContestSubmissionResponse(
                dispute_id=request.dispute_id,
                razorpay_status=data.get("status", "under_review"),
                razorpay_reference_id=data.get("id") or data.get("reference_id"),
                http_status_code=status_code,
                submitted_at=datetime.utcnow(),
                raw_response=data if isinstance(data, dict) else {"text": str(data)},
            )
        elif status_code == 400:
            raise RazorpayClientError(message=f"Bad Request: {resp.text}", status_code=400, dispute_id=request.dispute_id)
        elif status_code in (401, 403):
            raise RazorpayAuthenticationError(message=f"Authentication failed ({status_code}): {resp.text}", status_code=status_code, dispute_id=request.dispute_id)
        elif status_code == 404:
            raise RazorpayNotFoundError(message=f"Dispute not found: {request.dispute_id}", dispute_id=request.dispute_id)
        elif status_code == 409:
            raise RazorpayClientError(message=f"Conflict: Dispute already submitted or closed", status_code=409, dispute_id=request.dispute_id)
        elif status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            raise RazorpayRateLimitError(message="Rate limit exceeded", retry_after_sec=retry_after, dispute_id=request.dispute_id)
        elif status_code >= 500:
            raise RazorpayServerError(message=f"Razorpay Server Error ({status_code})", status_code=status_code, dispute_id=request.dispute_id)
        else:
            raise RazorpayClientError(message=f"Unexpected status code ({status_code}): {resp.text}", status_code=status_code, dispute_id=request.dispute_id)


# ---------------------------------------------------------------------------
# Mock Client Implementation for Testing & Offline Execution
# ---------------------------------------------------------------------------


class MockContestSubmissionClient:
    """
    Mock implementation of ContestSubmissionClient for offline testing & E2E execution.
    Contains zero network calls and supports configurable test failure modes.
    """

    def __init__(self, mode: str = "SUCCESS", custom_response: Optional[Dict[str, Any]] = None):
        self.mode = mode.upper()
        self.custom_response = custom_response
        self.submitted_requests: list[RazorpayContestSubmissionRequest] = []

    async def submit_contest(
        self, request: RazorpayContestSubmissionRequest
    ) -> RazorpayContestSubmissionResponse:
        self.submitted_requests.append(request)

        if self.mode == "SUCCESS":
            return RazorpayContestSubmissionResponse(
                dispute_id=request.dispute_id,
                razorpay_status="under_review",
                razorpay_reference_id=f"sub_ref_mock_{request.dispute_id}",
                http_status_code=200,
                submitted_at=datetime.utcnow(),
                raw_response=self.custom_response or {
                    "id": f"sub_ref_mock_{request.dispute_id}",
                    "entity": "dispute",
                    "status": "under_review",
                    "amount": request.amount_minor,
                    "currency": request.currency,
                },
            )
        elif self.mode == "HTTP_400":
            raise RazorpayClientError(message="Bad Request: Invalid contest submission payload", status_code=400, dispute_id=request.dispute_id)
        elif self.mode == "HTTP_401":
            raise RazorpayAuthenticationError(message="Unauthorized: Invalid API key secret", dispute_id=request.dispute_id)
        elif self.mode == "HTTP_403":
            raise RazorpayClientError(message="Forbidden: Insufficient account permissions", status_code=403, dispute_id=request.dispute_id)
        elif self.mode == "HTTP_404":
            raise RazorpayNotFoundError(message=f"Dispute not found: {request.dispute_id}", dispute_id=request.dispute_id)
        elif self.mode == "HTTP_409":
            raise RazorpayClientError(message="Conflict: Dispute already contested on Razorpay", status_code=409, dispute_id=request.dispute_id)
        elif self.mode == "HTTP_429":
            raise RazorpayRateLimitError(message="Rate limit exceeded", retry_after=5, dispute_id=request.dispute_id)
        elif self.mode == "HTTP_500":
            raise RazorpayServerError(message="Internal Server Error on Razorpay gateway", status_code=500, dispute_id=request.dispute_id)
        elif self.mode == "TIMEOUT":
            raise RazorpayNetworkError(message="Connection timed out after 15.0 seconds", dispute_id=request.dispute_id)
        elif self.mode == "CONNECTION_FAILURE":
            raise RazorpayNetworkError(message="Connection reset by peer", dispute_id=request.dispute_id)
        elif self.mode == "MALFORMED_RESPONSE":
            return RazorpayContestSubmissionResponse(
                dispute_id=request.dispute_id,
                razorpay_status="unknown_status",
                razorpay_reference_id=None,
                http_status_code=200,
                submitted_at=datetime.utcnow(),
                raw_response={"invalid_json": True},
            )
        else:
            raise RazorpayClientError(message=f"Unknown mock mode: {self.mode}", status_code=500, dispute_id=request.dispute_id)
