"""
Razorpay Service Layer — Business Logic Wrapper

Wraps the RazorpayClient with:
- Input validation and parameter bounding
- Error translation to HTTP exceptions
- Typed Pydantic schema returns

FINANCIAL SAFETY: This service is READ ONLY.
No database mutations. No Razorpay mutations.
No document methods. No placeholders for mutations.
"""

from __future__ import annotations

import logging
from fastapi import HTTPException

from backend.app.config import settings
from backend.app.schemas.razorpay import (
    RAZORPAY_DISPUTE_DOCUMENT_PURPOSES,
    SUPPORTED_EVIDENCE_MIME_TYPES,
    RazorpayDisputeListResponse,
    RazorpayDisputeResponse,
    RazorpayDocumentMetadataResponse,
)
from backend.app.services.evidence_reference_extractor import validate_document_id
from backend.app.services.razorpay_client import RazorpayClient
from backend.app.services.razorpay_errors import (
    RazorpayAuthenticationError,
    RazorpayClientError,
    RazorpayNetworkError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
    RazorpayServerError,
    RazorpayValidationError,
)

logger = logging.getLogger(__name__)


class RazorpayService:
    """
    Business logic layer for Razorpay dispute read operations.

    Translates RazorpayClientError subtypes into HTTP exceptions
    suitable for the API layer. No database writes. No mutations.
    """

    def __init__(self, client: RazorpayClient):
        self._client = client

    async def get_dispute(self, dispute_id: str) -> RazorpayDisputeResponse:
        """
        Fetch a single dispute from Razorpay by ID.

        Returns a validated RazorpayDisputeResponse.
        Raises HTTPException for all error cases.
        """
        if not dispute_id or not dispute_id.strip():
            raise HTTPException(status_code=400, detail="dispute_id is required")

        try:
            return await self._client.get_dispute(dispute_id)
        except RazorpayClientError as exc:
            raise self._translate_error(exc) from exc

    async def list_disputes(
        self, skip: int = 0, count: int = 50
    ) -> RazorpayDisputeListResponse:
        """
        List disputes from Razorpay with bounded pagination.

        count is capped at 100 (Razorpay maximum).
        skip must be >= 0.
        Returns a validated RazorpayDisputeListResponse.
        """
        skip = max(0, skip)
        count = max(1, min(count, 100))

        try:
            return await self._client.list_disputes(skip=skip, count=count)
        except RazorpayClientError as exc:
            raise self._translate_error(exc) from exc

    async def get_document_metadata(
        self, document_id: str
    ) -> RazorpayDocumentMetadataResponse:
        """
        Fetch and validate document metadata from Razorpay API.

        Performs:
        1. Security validation on document_id
        2. Read-only client fetch
        3. Pre-flight validation on purpose, MIME type, and size ceilings

        Returns a validated RazorpayDocumentMetadataResponse.
        Raises HTTPException for all error and pre-flight validation failures.
        """
        valid_id, err = validate_document_id(document_id)
        if not valid_id:
            raise HTTPException(
                status_code=400, detail=f"Invalid document_id: {err}"
            )

        try:
            metadata = await self._client.get_document_metadata(valid_id)
        except RazorpayClientError as exc:
            raise self._translate_error(exc) from exc

        # Application-level pre-flight validation
        self._validate_metadata_preflight(metadata)
        return metadata

    async def stream_document_content(
        self, document_id: str, max_allowed_bytes: int = 4_194_304
    ) -> DocumentContentStream:
        """
        Stream document binary content from Razorpay API (GET /v1/documents/:id/content).

        Validates document_id and returns DocumentContentStream for memory-safe chunked reading.
        Raises HTTPException for error failures.
        """
        valid_id, err = validate_document_id(document_id)
        if not valid_id:
            raise HTTPException(
                status_code=400, detail=f"Invalid document_id: {err}"
            )

        try:
            return await self._client.stream_document_content(
                valid_id, max_allowed_bytes=max_allowed_bytes
            )
        except RazorpayClientError as exc:
            raise self._translate_error(exc) from exc

    download_document_content = stream_document_content

    @staticmethod
    def _validate_metadata_preflight(
        metadata: RazorpayDocumentMetadataResponse,
    ) -> None:
        """
        Perform pre-flight application validation on document purpose, MIME type, and size.
        """
        if metadata.purpose not in RAZORPAY_DISPUTE_DOCUMENT_PURPOSES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid document purpose '{metadata.purpose}'. "
                    f"Expected one of: {sorted(RAZORPAY_DISPUTE_DOCUMENT_PURPOSES)}"
                ),
            )

        if metadata.mime_type not in SUPPORTED_EVIDENCE_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported document MIME type '{metadata.mime_type}'. "
                    f"Supported types: {sorted(SUPPORTED_EVIDENCE_MIME_TYPES)}"
                ),
            )

        # File size pre-flight ceilings
        if metadata.mime_type == "application/pdf":
            if metadata.size > settings.MAX_PDF_SIZE_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"PDF document metadata size ({metadata.size} bytes) exceeds "
                        f"maximum allowed ceiling of {settings.MAX_PDF_SIZE_BYTES} bytes."
                    ),
                )
        elif metadata.mime_type in ("image/jpeg", "image/jpg", "image/png"):
            if metadata.size > settings.MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Image document metadata size ({metadata.size} bytes) exceeds "
                        f"maximum allowed ceiling of {settings.MAX_IMAGE_SIZE_BYTES} bytes."
                    ),
                )

    @staticmethod
    def _translate_error(exc: RazorpayClientError) -> HTTPException:
        """
        Translate Razorpay client errors into appropriate HTTP exceptions.

        Never includes credentials or sensitive data in error details.
        """
        if exc.status_code == 403:
            return HTTPException(
                status_code=403,
                detail="Access to requested Razorpay document is forbidden.",
            )

        if isinstance(exc, RazorpayNotFoundError):
            return HTTPException(status_code=404, detail=exc.message)

        if isinstance(exc, RazorpayAuthenticationError):
            # Don't leak internal auth details — generic message
            return HTTPException(
                status_code=502,
                detail="Razorpay API authentication failed. Check server configuration.",
            )

        if isinstance(exc, RazorpayRateLimitError):
            return HTTPException(
                status_code=429,
                detail="Razorpay API rate limit exceeded. Please try again later.",
            )

        if isinstance(exc, RazorpayValidationError):
            return HTTPException(status_code=400, detail=exc.message)

        if isinstance(exc, RazorpayServerError):
            return HTTPException(
                status_code=502,
                detail="Razorpay API is temporarily unavailable.",
            )

        if isinstance(exc, RazorpayNetworkError):
            return HTTPException(
                status_code=502,
                detail="Unable to reach Razorpay API. Please try again later.",
            )

        # Catch-all for unknown errors
        logger.error("Unhandled Razorpay error: %s", exc.message)
        return HTTPException(
            status_code=502,
            detail="Unexpected error communicating with Razorpay.",
        )
