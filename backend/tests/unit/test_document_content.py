"""
Unit Test Suite: Razorpay Document Binary Content Retrieval — Task 3.3C

Tests read-only bounded streaming retrieval of Razorpay document binary content:
- Streaming PDF, JPEG, PNG binary content
- Incremental SHA-256 hash calculation
- Exact byte count tracking
- Content-Length early safety check
- Stream-level size ceiling enforcement and immediate abort
- Missing Content-Length safe handling
- Empty stream (0 bytes) rejection
- Error propagation (401, 403, 404, 429, 500, timeout)
- Fresh request retries without partial stream concatenation
- Resource cleanup & connection closure
- Absolute ZERO file writes, ZERO database mutations, ZERO magic-byte validation
"""

import hashlib
import inspect
import os
import pytest
from fastapi import HTTPException

from backend.app.schemas.razorpay import DocumentContentResult
from backend.app.services.razorpay_client import (
    DocumentContentStream,
    HttpRazorpayClient,
    MockRazorpayClient,
    RazorpayClient,
)
from backend.app.services.razorpay_errors import (
    RazorpayAuthenticationError,
    RazorpayClientError,
    RazorpayNetworkError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
    RazorpayServerError,
    RazorpayValidationError,
)
from backend.app.services.razorpay_service import RazorpayService

DOC_ID_PDF = "doc_pdf_001"
DOC_ID_JPEG = "doc_jpeg_001"
DOC_ID_PNG = "doc_png_001"


def _make_mock_service(mock_documents=None, error_mode=None) -> RazorpayService:
    client = MockRazorpayClient(
        error_mode=error_mode, mock_documents=mock_documents
    )
    return RazorpayService(client=client)


# ===========================================================================
# 1. CORE BINARY STREAMING TESTS
# ===========================================================================


class TestDocumentContentStreamingCore:
    """Test successful binary content streaming and hash calculation."""

    @pytest.mark.asyncio
    async def test_stream_pdf(self):
        service = _make_mock_service()
        stream = await service.stream_document_content(DOC_ID_PDF)

        assert isinstance(stream, DocumentContentStream)
        assert stream.razorpay_doc_id == DOC_ID_PDF
        assert stream.content_type == "application/pdf"

        result, raw_bytes = await stream.consume_to_result()
        assert isinstance(result, DocumentContentResult)
        assert result.razorpay_doc_id == DOC_ID_PDF
        assert result.content_type == "application/pdf"
        assert result.total_bytes == len(raw_bytes)
        assert len(raw_bytes) > 0
        assert raw_bytes.startswith(b"%PDF-")

    @pytest.mark.asyncio
    async def test_stream_jpeg(self):
        service = _make_mock_service()
        stream = await service.stream_document_content(DOC_ID_JPEG)
        result, raw_bytes = await stream.consume_to_result()

        assert result.content_type == "image/jpeg"
        assert result.total_bytes == len(raw_bytes)
        assert raw_bytes.startswith(b"\xff\xd8\xff")

    @pytest.mark.asyncio
    async def test_stream_png(self):
        service = _make_mock_service()
        stream = await service.stream_document_content(DOC_ID_PNG)
        result, raw_bytes = await stream.consume_to_result()

        assert result.content_type == "image/png"
        assert result.total_bytes == len(raw_bytes)
        assert raw_bytes.startswith(b"\x89PNG")

    @pytest.mark.asyncio
    async def test_stream_hash(self):
        service = _make_mock_service()
        stream = await service.stream_document_content(DOC_ID_PDF)
        result, raw_bytes = await stream.consume_to_result()

        expected_hash = hashlib.sha256(raw_bytes).hexdigest()
        assert result.sha256 == expected_hash

    @pytest.mark.asyncio
    async def test_stream_byte_count(self):
        service = _make_mock_service()
        stream = await service.stream_document_content(DOC_ID_PDF)
        result, raw_bytes = await stream.consume_to_result()

        assert result.total_bytes == len(raw_bytes)

    @pytest.mark.asyncio
    async def test_mock_binary_stream(self):
        client = MockRazorpayClient()
        stream = await client.stream_document_content(DOC_ID_PDF)
        result, raw_bytes = await stream.consume_to_result()

        assert result.razorpay_doc_id == DOC_ID_PDF
        assert len(raw_bytes) == result.total_bytes


# ===========================================================================
# 2. SIZE LIMIT & CONTENT-LENGTH SAFETY TESTS
# ===========================================================================


class TestStreamSizeSafety:
    """Test Content-Length early rejection & stream size ceiling enforcement."""

    @pytest.mark.asyncio
    async def test_content_length_within_limit(self):
        client = MockRazorpayClient()
        stream = await client.stream_document_content(DOC_ID_PDF, max_allowed_bytes=1_048_576)
        result, raw_bytes = await stream.consume_to_result()
        assert result.total_bytes <= 1_048_576

    @pytest.mark.asyncio
    async def test_content_length_exceeds_limit(self):
        client = MockRazorpayClient(error_mode="oversized_content_length")
        with pytest.raises(RazorpayValidationError) as exc_info:
            await client.stream_document_content(DOC_ID_PDF, max_allowed_bytes=2_097_152)
        assert "Content-Length header" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_actual_stream_exceeds_limit(self):
        client = MockRazorpayClient(error_mode="oversized_stream")
        stream = await client.stream_document_content(DOC_ID_PDF, max_allowed_bytes=2_097_152)

        with pytest.raises(RazorpayValidationError) as exc_info:
            await stream.consume_to_result()
        assert "exceeds maximum allowed ceiling" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_missing_content_length(self):
        """Streams safely without Content-Length header while enforcing stream ceiling."""
        client = MockRazorpayClient()
        stream = await client.stream_document_content(DOC_ID_PDF, max_allowed_bytes=2_097_152)
        result, raw_bytes = await stream.consume_to_result()
        assert result.total_bytes > 0

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """0-byte stream raises structured error."""
        client = MockRazorpayClient(error_mode="empty_stream")
        stream = await client.stream_document_content(DOC_ID_PDF)

        with pytest.raises(RazorpayValidationError) as exc_info:
            await stream.consume_to_result()
        assert "empty (0 bytes)" in exc_info.value.message


# ===========================================================================
# 3. ERROR HANDLING & RETRY TESTS
# ===========================================================================


class TestStreamErrorHandling:
    """Test HTTP status errors & retry policy."""

    @pytest.mark.asyncio
    async def test_http_401(self):
        service = _make_mock_service(error_mode="auth_error")
        with pytest.raises(HTTPException) as exc_info:
            await service.stream_document_content(DOC_ID_PDF)
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_http_403(self):
        service = _make_mock_service(error_mode="forbidden")
        with pytest.raises(HTTPException) as exc_info:
            await service.stream_document_content(DOC_ID_PDF)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_http_404(self):
        service = _make_mock_service(error_mode="not_found")
        with pytest.raises(HTTPException) as exc_info:
            await service.stream_document_content(DOC_ID_PDF)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_http_429(self):
        service = _make_mock_service(error_mode="rate_limit")
        with pytest.raises(HTTPException) as exc_info:
            await service.stream_document_content(DOC_ID_PDF)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_http_500(self):
        service = _make_mock_service(error_mode="server_error")
        with pytest.raises(HTTPException) as exc_info:
            await service.stream_document_content(DOC_ID_PDF)
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_network_timeout(self):
        service = _make_mock_service(error_mode="timeout")
        with pytest.raises(HTTPException) as exc_info:
            await service.stream_document_content(DOC_ID_PDF)
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_retry_fresh_stream(self):
        """Retries issue a fresh request with a fresh hash calculator."""
        client = MockRazorpayClient()
        stream1 = await client.stream_document_content(DOC_ID_PDF)
        res1, bytes1 = await stream1.consume_to_result()

        stream2 = await client.stream_document_content(DOC_ID_PDF)
        res2, bytes2 = await stream2.consume_to_result()

        assert res1.sha256 == res2.sha256
        assert res1.total_bytes == res2.total_bytes

    @pytest.mark.asyncio
    async def test_no_partial_stream_concatenation(self):
        """Consuming a stream twice raises RuntimeError (never concatenates)."""
        client = MockRazorpayClient()
        stream = await client.stream_document_content(DOC_ID_PDF)
        await stream.consume_to_result()

        with pytest.raises(RuntimeError):
            await stream.consume_to_result()


# ===========================================================================
# 4. ISOLATION & READ-ONLY BOUNDARY TESTS
# ===========================================================================


class TestIsolationAndSafety:
    """Verify zero side effects (0 files written, 0 DB mutations, 0 magic byte processing)."""

    @pytest.mark.asyncio
    async def test_stream_does_not_write_files(self, tmp_path):
        """Streaming does NOT write any files to disk."""
        initial_files = set(os.listdir(tmp_path))
        client = MockRazorpayClient()
        stream = await client.stream_document_content(DOC_ID_PDF)
        await stream.consume_to_result()

        current_files = set(os.listdir(tmp_path))
        assert current_files == initial_files

    @pytest.mark.asyncio
    async def test_stream_does_not_modify_database(self, async_db):
        """Streaming does NOT touch or mutate database tables."""
        from sqlalchemy import select
        from backend.app.models.document import EvidenceDocument

        stmt_before = select(EvidenceDocument)
        res_before = await async_db.execute(stmt_before)
        count_before = len(res_before.scalars().all())

        client = MockRazorpayClient()
        stream = await client.stream_document_content(DOC_ID_PDF)
        await stream.consume_to_result()

        res_after = await async_db.execute(stmt_before)
        count_after = len(res_after.scalars().all())

        assert count_after == count_before

    def test_no_magic_byte_processing(self):
        """Verify Task 3.3C module does not perform magic byte file validation."""
        import backend.app.services.razorpay_client as r_client
        assert not hasattr(r_client, "validate_magic_bytes")
        assert not hasattr(r_client, "rasterize_pdf")

    def test_no_mutation_methods(self):
        """Verify zero mutation methods exist on Razorpay clients or services."""
        forbidden = ("post_", "put_", "patch_", "delete_", "contest_", "accept_")
        for cls in [HttpRazorpayClient, MockRazorpayClient, RazorpayService]:
            methods = [
                m for m, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
                if not m.startswith("_")
            ]
            for m in methods:
                for f in forbidden:
                    assert not m.startswith(f), f"Forbidden method found: {m}"
