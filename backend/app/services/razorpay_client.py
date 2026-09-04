"""
Razorpay API Client Abstraction — READ ONLY

Provides a Protocol-based client interface with two implementations:
1. HttpRazorpayClient — makes real HTTP calls to Razorpay API (read-only)
2. MockRazorpayClient — returns deterministic data for testing

FINANCIAL SAFETY: This module contains ONLY GET operations.
No POST, PATCH, PUT, DELETE methods exist.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import AsyncIterator, Protocol, runtime_checkable

import httpx

from backend.app.config import Settings
from backend.app.schemas.razorpay import (
    DocumentContentResult,
    RazorpayDisputeListResponse,
    RazorpayDisputeResponse,
    RazorpayDocumentMetadataResponse,
)
from backend.app.services.evidence_reference_extractor import validate_document_id
from backend.app.services.razorpay_errors import (
    RazorpayAuthenticationError,
    RazorpayClientError,
    RazorpayNetworkError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
    RazorpayServerError,
    RazorpayUnknownError,
    RazorpayValidationError,
)

logger = logging.getLogger(__name__)

# Credential-related field names that must NEVER appear in logs
_SENSITIVE_FIELDS = {"key_id", "key_secret", "authorization", "auth"}


# ---------------------------------------------------------------------------
# Streaming Container
# ---------------------------------------------------------------------------


class DocumentContentStream:
    """
    Bounded streaming abstraction for Razorpay document binary content.

    Security & Safety Guarantees:
    - Streams raw byte chunks (default 64 KB = 65,536 bytes)
    - Enforces maximum allowed byte ceiling during streaming
    - Aborts immediately and closes HTTP stream if total_bytes > max_allowed_bytes
    - Computes SHA-256 hex digest incrementally while streaming
    - Ensures full resource cleanup (stream closed) on completion or error
    - Does NOT write files or store unbounded content in RAM
    """

    def __init__(
        self,
        razorpay_doc_id: str,
        content_type: str,
        raw_response: httpx.Response | None,
        max_allowed_bytes: int = 4_194_304,
        chunk_size: int = 65536,
        mock_chunks: list[bytes] | None = None,
    ):
        self.razorpay_doc_id = razorpay_doc_id
        self.content_type = content_type
        self._response = raw_response
        self.max_allowed_bytes = max_allowed_bytes
        self.chunk_size = chunk_size
        self._mock_chunks = mock_chunks
        self.total_bytes = 0
        self.sha256 = ""
        self._consumed = False

    async def chunks(self) -> AsyncIterator[bytes]:
        """
        Yields raw byte chunks (64KB default).
        Updates SHA-256 and byte counter incrementally.
        Aborts and closes HTTP stream immediately if total_bytes > max_allowed_bytes.
        """
        if self._consumed:
            raise RuntimeError("DocumentContentStream has already been consumed")
        self._consumed = True

        hasher = hashlib.sha256()

        try:
            if self._mock_chunks is not None:
                for chunk in self._mock_chunks:
                    if not chunk:
                        continue
                    self.total_bytes += len(chunk)
                    if self.total_bytes > self.max_allowed_bytes:
                        raise RazorpayValidationError(
                            message=(
                                f"Streamed document content size ({self.total_bytes} bytes) "
                                f"exceeds maximum allowed ceiling of {self.max_allowed_bytes} bytes"
                            ),
                            dispute_id=self.razorpay_doc_id,
                        )
                    hasher.update(chunk)
                    yield chunk
            elif self._response is not None:
                async for chunk in self._response.aiter_bytes(chunk_size=self.chunk_size):
                    if not chunk:
                        continue
                    self.total_bytes += len(chunk)
                    if self.total_bytes > self.max_allowed_bytes:
                        await self._response.aclose()
                        raise RazorpayValidationError(
                            message=(
                                f"Streamed document content size ({self.total_bytes} bytes) "
                                f"exceeds maximum allowed ceiling of {self.max_allowed_bytes} bytes"
                            ),
                            dispute_id=self.razorpay_doc_id,
                        )
                    hasher.update(chunk)
                    yield chunk

            if self.total_bytes == 0:
                raise RazorpayValidationError(
                    message="Downloaded document content stream is empty (0 bytes)",
                    dispute_id=self.razorpay_doc_id,
                )

            self.sha256 = hasher.hexdigest()

        finally:
            if self._response is not None:
                await self._response.aclose()

    async def consume_to_result(self) -> tuple[DocumentContentResult, bytes]:
        """
        Helper method to consume stream into memory for testing/verification.
        Enforces all security limits and returns (DocumentContentResult, raw_bytes).
        """
        chunks_list = []
        async for chunk in self.chunks():
            chunks_list.append(chunk)

        raw_bytes = b"".join(chunks_list)
        result = DocumentContentResult(
            razorpay_doc_id=self.razorpay_doc_id,
            content_type=self.content_type,
            total_bytes=self.total_bytes,
            sha256=self.sha256,
        )
        return result, raw_bytes


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class RazorpayClient(Protocol):
    """
    Read-only protocol for Razorpay dispute API access.

    No mutation methods (POST/PATCH/PUT/DELETE) are defined.
    Implementations MUST return typed Pydantic schemas, not raw dicts.
    """

    async def get_dispute(self, dispute_id: str) -> RazorpayDisputeResponse: ...

    async def list_disputes(
        self, skip: int = 0, count: int = 50
    ) -> RazorpayDisputeListResponse: ...

    async def get_document_metadata(
        self, document_id: str
    ) -> RazorpayDocumentMetadataResponse: ...

    async def stream_document_content(
        self, document_id: str, max_allowed_bytes: int = 4_194_304
    ) -> DocumentContentStream: ...

    async def download_document_content(
        self, document_id: str, max_allowed_bytes: int = 4_194_304
    ) -> DocumentContentStream: ...


# ---------------------------------------------------------------------------
# HTTP Client Implementation
# ---------------------------------------------------------------------------


class HttpRazorpayClient:
    """
    Production Razorpay API client using httpx.

    - Uses HTTP Basic Auth (key_id:key_secret)
    - Bounded exponential retry for 5xx/network errors
    - Respects Retry-After for 429 (bounded)
    - No retry for 400/401/404
    - Never retries indefinitely
    - Returns typed Pydantic schemas, not raw dicts
    - Never logs credentials
    """

    def __init__(self, settings: Settings):
        self._base_url = settings.RAZORPAY_API_BASE_URL.rstrip("/")
        self._auth = (settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        self._max_retries = settings.RAZORPAY_MAX_RETRIES
        self._timeout = httpx.Timeout(
            timeout=settings.RAZORPAY_READ_TIMEOUT,
            connect=settings.RAZORPAY_CONNECT_TIMEOUT,
            read=settings.RAZORPAY_READ_TIMEOUT,
            write=settings.RAZORPAY_READ_TIMEOUT,
            pool=10.0,
        )
        # Maximum wait time for Retry-After header (seconds)
        self._max_retry_after = 60.0

    async def get_dispute(self, dispute_id: str) -> RazorpayDisputeResponse:
        """Fetch a single dispute by ID from Razorpay API."""
        if not dispute_id or not dispute_id.strip():
            raise RazorpayValidationError(
                message="dispute_id must be a non-empty string",
                dispute_id=dispute_id,
            )

        url = f"{self._base_url}/v1/disputes/{dispute_id}"
        data = await self._request_with_retry("get_dispute", url, dispute_id=dispute_id)

        # Validate into typed schema
        try:
            return RazorpayDisputeResponse.model_validate(data)
        except Exception as exc:
            raise RazorpayValidationError(
                message=f"Invalid dispute response from Razorpay: {exc}",
                dispute_id=dispute_id,
            ) from exc

    async def list_disputes(
        self, skip: int = 0, count: int = 50
    ) -> RazorpayDisputeListResponse:
        """List disputes from Razorpay API with pagination."""
        # Bound parameters
        count = max(1, min(count, 100))
        skip = max(0, skip)

        url = f"{self._base_url}/v1/disputes"
        params = {"skip": skip, "count": count}
        data = await self._request_with_retry("list_disputes", url, params=params)

        # Validate into typed schema
        try:
            return RazorpayDisputeListResponse.model_validate(data)
        except Exception as exc:
            raise RazorpayValidationError(
                message=f"Invalid dispute list response from Razorpay: {exc}",
            ) from exc

    async def get_document_metadata(
        self, document_id: str
    ) -> RazorpayDocumentMetadataResponse:
        """Fetch document metadata by ID from Razorpay API."""
        valid_id, err = validate_document_id(document_id)
        if not valid_id:
            raise RazorpayValidationError(
                message=f"document_id must be valid: {err}",
                dispute_id=None,
            )

        url = f"{self._base_url}/v1/documents/{valid_id}"
        data = await self._request_with_retry(
            "get_document_metadata", url, dispute_id=valid_id
        )

        try:
            return RazorpayDocumentMetadataResponse.model_validate(data)
        except Exception as exc:
            raise RazorpayValidationError(
                message=f"Invalid document metadata response from Razorpay: {exc}",
                dispute_id=valid_id,
            ) from exc

    async def stream_document_content(
        self, document_id: str, max_allowed_bytes: int = 4_194_304
    ) -> DocumentContentStream:
        """
        Stream document binary content from GET /v1/documents/:id/content.

        Performs:
        1. Input validation on document_id
        2. Content-Length early safety check
        3. Returns DocumentContentStream wrapper for bounded 64KB chunk streaming
        4. Fresh request retries on 5xx/network errors (never resumes partial streams)
        """
        valid_id, err = validate_document_id(document_id)
        if not valid_id:
            raise RazorpayValidationError(
                message=f"document_id must be valid: {err}",
                dispute_id=None,
            )

        url = f"{self._base_url}/v1/documents/{valid_id}/content"

        for attempt in range(self._max_retries + 1):
            try:
                client = httpx.AsyncClient(auth=self._auth, timeout=self._timeout)
                response = await client.send(
                    client.build_request("GET", url), stream=True
                )

                logger.info(
                    "Razorpay API stream_document_content status=%d attempt=%d/%d document_id=%s",
                    response.status_code,
                    attempt + 1,
                    self._max_retries + 1,
                    valid_id,
                )

                if response.status_code == 200:
                    content_len_hdr = response.headers.get("Content-Length")
                    if content_len_hdr:
                        try:
                            content_len = int(content_len_hdr)
                            if content_len > max_allowed_bytes:
                                await response.aclose()
                                raise RazorpayValidationError(
                                    message=(
                                        f"Content-Length header ({content_len} bytes) exceeds "
                                        f"maximum allowed ceiling of {max_allowed_bytes} bytes"
                                    ),
                                    dispute_id=valid_id,
                                )
                        except ValueError:
                            pass

                    content_type = response.headers.get(
                        "Content-Type", "application/octet-stream"
                    )

                    return DocumentContentStream(
                        razorpay_doc_id=valid_id,
                        content_type=content_type,
                        raw_response=response,
                        max_allowed_bytes=max_allowed_bytes,
                    )

                if response.status_code == 401:
                    await response.aclose()
                    raise RazorpayAuthenticationError(dispute_id=valid_id)

                if response.status_code == 403:
                    await response.aclose()
                    raise RazorpayClientError(
                        message="Access forbidden", status_code=403, dispute_id=valid_id
                    )

                if response.status_code == 404:
                    await response.aclose()
                    raise RazorpayNotFoundError(
                        message=f"Document content not found: {valid_id}", dispute_id=valid_id
                    )

                if response.status_code == 400:
                    await response.aclose()
                    raise RazorpayValidationError(
                        message="Invalid document content request", dispute_id=valid_id
                    )

                if response.status_code == 429:
                    retry_after = self._parse_retry_after(response)
                    await response.aclose()
                    if attempt < self._max_retries:
                        wait_time = min(retry_after, self._max_retry_after)
                        await asyncio.sleep(wait_time)
                        continue
                    raise RazorpayRateLimitError(
                        retry_after=retry_after, dispute_id=valid_id
                    )

                if 500 <= response.status_code < 600:
                    await response.aclose()
                    if attempt < self._max_retries:
                        backoff = 2**attempt
                        await asyncio.sleep(backoff)
                        continue
                    raise RazorpayServerError(
                        message=f"Server error {response.status_code}",
                        status_code=response.status_code,
                        dispute_id=valid_id,
                    )

                await response.aclose()
                raise RazorpayServerError(
                    message=f"Unexpected status code {response.status_code}",
                    dispute_id=valid_id,
                )

            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                if attempt < self._max_retries:
                    backoff = 2**attempt
                    await asyncio.sleep(backoff)
                    continue
                raise RazorpayNetworkError(
                    message=f"Network error streaming document: {exc}",
                    dispute_id=valid_id,
                ) from exc

    download_document_content = stream_document_content

    # -----------------------------------------------------------------------
    # Internal HTTP request engine with retry
    # -----------------------------------------------------------------------

    async def _request_with_retry(
        self,
        operation: str,
        url: str,
        dispute_id: str | None = None,
        params: dict | None = None,
    ) -> dict:
        """
        Execute a GET request with bounded exponential retry.

        Retry policy:
        - 5xx / network: retry with exponential backoff
        - 429: respect Retry-After (bounded), then retry
        - 400/401/403/404: raise immediately, no retry
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            start_time = time.monotonic()

            try:
                async with httpx.AsyncClient(
                    auth=self._auth,
                    timeout=self._timeout,
                ) as client:
                    response = await client.get(url, params=params)

                latency_ms = (time.monotonic() - start_time) * 1000

                # Log safely (never include credentials)
                logger.info(
                    "Razorpay API %s status=%d latency=%.1fms attempt=%d/%d dispute_id=%s",
                    operation,
                    response.status_code,
                    latency_ms,
                    attempt + 1,
                    self._max_retries + 1,
                    dispute_id or "N/A",
                )

                # Handle by status code
                if response.status_code == 200:
                    return self._parse_response(response, operation, dispute_id)

                if response.status_code == 401:
                    raise RazorpayAuthenticationError(dispute_id=dispute_id)

                if response.status_code == 403:
                    error_msg = self._extract_error_message(response)
                    raise RazorpayClientError(
                        message=f"Access forbidden: {error_msg}",
                        status_code=403,
                        dispute_id=dispute_id,
                    )

                if response.status_code == 404:
                    raise RazorpayNotFoundError(
                        message=f"Resource not found: {dispute_id}",
                        dispute_id=dispute_id,
                    )

                if response.status_code == 400:
                    error_msg = self._extract_error_message(response)
                    raise RazorpayValidationError(
                        message=error_msg,
                        dispute_id=dispute_id,
                    )

                if response.status_code == 429:
                    retry_after = self._parse_retry_after(response)
                    if attempt < self._max_retries:
                        wait_time = min(retry_after, self._max_retry_after)
                        logger.warning(
                            "Razorpay rate limit hit, waiting %.1fs before retry",
                            wait_time,
                        )
                        await asyncio.sleep(wait_time)
                        last_error = RazorpayRateLimitError(
                            retry_after=retry_after, dispute_id=dispute_id
                        )
                        continue
                    raise RazorpayRateLimitError(
                        retry_after=retry_after, dispute_id=dispute_id
                    )

                if 500 <= response.status_code < 600:
                    if attempt < self._max_retries:
                        backoff = 2**attempt  # 1s, 2s, 4s
                        logger.warning(
                            "Razorpay server error %d, retrying in %ds",
                            response.status_code,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        last_error = RazorpayServerError(
                            message=f"Server error {response.status_code}",
                            status_code=response.status_code,
                            dispute_id=dispute_id,
                        )
                        continue
                    raise RazorpayServerError(
                        message=f"Server error {response.status_code} after {self._max_retries + 1} attempts",
                        status_code=response.status_code,
                        dispute_id=dispute_id,
                    )

                # Unknown status code — no retry
                raise RazorpayUnknownError(
                    message=f"Unexpected status code {response.status_code}",
                    status_code=response.status_code,
                    dispute_id=dispute_id,
                )

            except RazorpayClientError:
                raise  # Already classified — propagate
            except httpx.TimeoutException as exc:
                latency_ms = (time.monotonic() - start_time) * 1000
                logger.warning(
                    "Razorpay API timeout for %s after %.1fms attempt=%d/%d",
                    operation,
                    latency_ms,
                    attempt + 1,
                    self._max_retries + 1,
                )
                if attempt < self._max_retries:
                    backoff = 2**attempt
                    await asyncio.sleep(backoff)
                    last_error = RazorpayNetworkError(
                        message=f"Timeout after {latency_ms:.0f}ms",
                        dispute_id=dispute_id,
                    )
                    continue
                raise RazorpayNetworkError(
                    message=f"Timeout after {self._max_retries + 1} attempts",
                    dispute_id=dispute_id,
                ) from exc
            except httpx.HTTPError as exc:
                latency_ms = (time.monotonic() - start_time) * 1000
                logger.warning(
                    "Razorpay API network error for %s: %s attempt=%d/%d",
                    operation,
                    type(exc).__name__,
                    attempt + 1,
                    self._max_retries + 1,
                )
                if attempt < self._max_retries:
                    backoff = 2**attempt
                    await asyncio.sleep(backoff)
                    last_error = RazorpayNetworkError(
                        message=str(exc), dispute_id=dispute_id
                    )
                    continue
                raise RazorpayNetworkError(
                    message=f"Network error after {self._max_retries + 1} attempts: {exc}",
                    dispute_id=dispute_id,
                ) from exc

        # Should not reach here, but safety net
        if last_error:
            raise last_error
        raise RazorpayUnknownError(message="Request failed with no error captured")

    def _parse_response(
        self,
        response: httpx.Response,
        operation: str,
        dispute_id: str | None,
    ) -> dict:
        """Parse JSON response, checking for Razorpay error payloads."""
        try:
            data = response.json()
        except Exception as exc:
            raise RazorpayValidationError(
                message=f"Malformed JSON response from Razorpay for {operation}",
                dispute_id=dispute_id,
            ) from exc

        # Razorpay wraps errors in an "error" key even on 200 in some edge cases
        if isinstance(data, dict) and "error" in data:
            error_info = data["error"]
            raise RazorpayValidationError(
                message=error_info.get("description", "Unknown error"),
                dispute_id=dispute_id,
                raw_error_code=error_info.get("code"),
            )

        return data

    def _extract_error_message(self, response: httpx.Response) -> str:
        """Safely extract error message from non-200 response."""
        try:
            data = response.json()
            if isinstance(data, dict) and "error" in data:
                return data["error"].get("description", f"HTTP {response.status_code}")
        except Exception:
            pass
        return f"HTTP {response.status_code}"

    def _parse_retry_after(self, response: httpx.Response) -> float:
        """Parse Retry-After header, default to 1s if absent or invalid."""
        try:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                return float(retry_after)
        except (ValueError, TypeError):
            pass
        return 1.0


# ---------------------------------------------------------------------------
# Mock Client Implementation
# ---------------------------------------------------------------------------


class MockRazorpayClient:
    """
    Deterministic mock Razorpay client for testing.

    - Returns typed Pydantic schemas
    - Supports configurable error injection
    - No network calls, no real credentials
    - Only has get_dispute and list_disputes — no mutation methods
    """

    def __init__(
        self,
        error_mode: str | None = None,
        mock_disputes: dict[str, dict] | None = None,
        mock_documents: dict[str, dict] | None = None,
        mock_streams: dict[str, bytes] | None = None,
    ):
        """
        Initialize MockRazorpayClient.

        Args:
            error_mode: One of 'not_found', 'auth_error', 'forbidden', 'rate_limit',
                       'server_error', 'timeout', 'malformed', or None.
            mock_disputes: Optional mapping of dispute_id -> raw dispute dict.
            mock_documents: Optional mapping of document_id -> raw document dict.
            mock_streams: Optional mapping of document_id -> raw binary content bytes.
        """
        self._error_mode = error_mode
        self._mock_disputes = mock_disputes or {}
        self._mock_documents = mock_documents or {}
        self._mock_streams = mock_streams or {}

    async def get_dispute(self, dispute_id: str) -> RazorpayDisputeResponse:
        """Return a mock dispute or raise a configured error."""
        self._maybe_raise_error(dispute_id)

        if dispute_id in self._mock_disputes:
            return RazorpayDisputeResponse.model_validate(
                self._mock_disputes[dispute_id]
            )

        # Default mock dispute
        return RazorpayDisputeResponse.model_validate(
            self._default_dispute(dispute_id)
        )

    async def list_disputes(
        self, skip: int = 0, count: int = 50
    ) -> RazorpayDisputeListResponse:
        """Return a mock paginated dispute list or raise a configured error."""
        self._maybe_raise_error(None)

        count = max(1, min(count, 100))
        all_disputes = list(self._mock_disputes.values())

        # Generate defaults if no mock data
        if not all_disputes:
            all_disputes = [
                self._default_dispute(f"disp_mock_{i}") for i in range(3)
            ]

        page = all_disputes[skip : skip + count]
        items = [RazorpayDisputeResponse.model_validate(d) for d in page]

        return RazorpayDisputeListResponse(
            entity="collection",
            count=len(items),
            items=items,
        )

    async def get_document_metadata(
        self, document_id: str
    ) -> RazorpayDocumentMetadataResponse:
        """Return mock document metadata or raise a configured error."""
        valid_id, err = validate_document_id(document_id)
        if not valid_id:
            raise RazorpayValidationError(
                message=f"Invalid document_id: {err}",
                dispute_id=None,
            )
        self._maybe_raise_error(valid_id)

        if valid_id in self._mock_documents:
            return RazorpayDocumentMetadataResponse.model_validate(
                self._mock_documents[valid_id]
            )

        return RazorpayDocumentMetadataResponse.model_validate(
            self._default_document(valid_id)
        )

    async def stream_document_content(
        self, document_id: str, max_allowed_bytes: int = 4_194_304
    ) -> DocumentContentStream:
        """Return a mock DocumentContentStream or raise a configured error."""
        valid_id, err = validate_document_id(document_id)
        if not valid_id:
            raise RazorpayValidationError(
                message=f"Invalid document_id: {err}", dispute_id=None
            )
        self._maybe_raise_error(valid_id)

        if self._error_mode == "empty_stream":
            mock_chunks = []
            content_type = "application/pdf"
        elif self._error_mode == "oversized_stream":
            mock_chunks = [b"A" * (max_allowed_bytes + 1024)]
            content_type = "application/pdf"
        elif self._error_mode == "oversized_content_length":
            raise RazorpayValidationError(
                message=(
                    f"Content-Length header (5242880 bytes) exceeds "
                    f"maximum allowed ceiling of {max_allowed_bytes} bytes"
                ),
                dispute_id=valid_id,
            )
        elif valid_id in self._mock_streams:
            mock_bytes = self._mock_streams[valid_id]
            meta = self._mock_documents.get(valid_id, {})
            content_type = meta.get("mime_type", "application/pdf")
            mock_chunks = [mock_bytes[:256], mock_bytes[256:]] if len(mock_bytes) > 256 else [mock_bytes]
        else:
            if "jpeg" in document_id or "jpg" in document_id:
                mock_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF mock jpeg content for " + valid_id.encode() + b" " + b"0" * 400
                content_type = "image/jpeg"
            elif "png" in document_id:
                mock_bytes = b"\x89PNG\r\n\x1a\n mock png content for " + valid_id.encode() + b" " + b"0" * 400
                content_type = "image/png"
            else:
                mock_bytes = b"%PDF-1.4 mock pdf content for " + valid_id.encode() + b" " + b"0" * 500
                content_type = "application/pdf"

            mock_chunks = [mock_bytes[:256], mock_bytes[256:]]

        return DocumentContentStream(
            razorpay_doc_id=valid_id,
            content_type=content_type,
            raw_response=None,
            max_allowed_bytes=max_allowed_bytes,
            mock_chunks=mock_chunks,
        )

    download_document_content = stream_document_content

    def _maybe_raise_error(self, dispute_id: str | None) -> None:
        """Raise a configured error for testing."""
        if self._error_mode == "not_found":
            raise RazorpayNotFoundError(dispute_id=dispute_id)
        if self._error_mode == "auth_error":
            raise RazorpayAuthenticationError(dispute_id=dispute_id)
        if self._error_mode == "forbidden":
            raise RazorpayClientError(
                message="Access forbidden", status_code=403, dispute_id=dispute_id
            )
        if self._error_mode == "rate_limit":
            raise RazorpayRateLimitError(retry_after=5.0, dispute_id=dispute_id)
        if self._error_mode == "server_error":
            raise RazorpayServerError(dispute_id=dispute_id)
        if self._error_mode == "timeout":
            raise RazorpayNetworkError(
                message="Connection timeout", dispute_id=dispute_id
            )
        if self._error_mode == "malformed":
            raise RazorpayValidationError(
                message="Malformed response", dispute_id=dispute_id
            )

    @staticmethod
    def _default_document(document_id: str) -> dict:
        """Generate a deterministic default mock document metadata dict."""
        return {
            "id": document_id if document_id.startswith("doc_") else f"doc_{document_id}",
            "entity": "document",
            "purpose": "dispute_evidence",
            "name": f"evidence_{document_id}.pdf",
            "size": 524288,
            "mime_type": "application/pdf",
            "created_at": 1735603200,
        }

    @staticmethod
    def _default_dispute(dispute_id: str) -> dict:
        """Generate a deterministic default mock dispute."""
        return {
            "id": dispute_id if dispute_id.startswith("disp_") else f"disp_{dispute_id}",
            "entity": "dispute",
            "payment_id": f"pay_mock_{dispute_id[-8:]}",
            "amount": 150000,  # 1500.00 INR in paise
            "currency": "INR",
            "amount_deducted": 150000,
            "reason_code": "chargeback",
            "reason_description": "Product not delivered",
            "respond_by": 1735689600,  # Fixed mock timestamp
            "status": "open",
            "phase": "chargeback",
            "created_at": 1735603200,  # Fixed mock timestamp
        }
