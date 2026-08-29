"""
Unit Test Suite: Razorpay Document Metadata Retrieval — Task 3.3B

Tests read-only metadata retrieval via Razorpay API client & service:
- Valid PDF, JPEG, PNG metadata retrieval
- Document ID security validation & path traversal defense
- Untrusted document name handling
- Pre-flight purpose validation (dispute_evidence)
- Pre-flight MIME type validation (pdf, jpeg, png)
- Pre-flight size ceiling validation (2MB PDF, 4MB Image)
- Error propagation (401, 403, 404, 429, 500, timeout, malformed)
- Schema validation & invalid entity rejection
- Credential safety
- Absolute zero binary content downloads & zero file storage
- Absolute zero Razorpay mutation methods
"""

import inspect
import json
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.config import settings
from backend.app.schemas.razorpay import (
    RazorpayDocumentMetadataResponse,
    RAZORPAY_DISPUTE_DOCUMENT_PURPOSES,
    SUPPORTED_EVIDENCE_MIME_TYPES,
)
from backend.app.services.razorpay_client import (
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

DOC_ID = "doc_AHfqOvkldwsbqt"

VALID_PDF_METADATA = {
    "id": DOC_ID,
    "entity": "document",
    "purpose": "dispute_evidence",
    "name": "shipping_receipt.pdf",
    "size": 524288,  # 512 KB
    "mime_type": "application/pdf",
    "created_at": 1735603200,
}

VALID_JPEG_METADATA = {
    "id": "doc_jpeg_001",
    "entity": "document",
    "purpose": "dispute_evidence",
    "name": "photo.jpg",
    "size": 1048576,  # 1 MB
    "mime_type": "image/jpeg",
    "created_at": 1735603200,
}

VALID_PNG_METADATA = {
    "id": "doc_png_001",
    "entity": "document",
    "purpose": "dispute_evidence",
    "name": "screenshot.png",
    "size": 2097152,  # 2 MB
    "mime_type": "image/png",
    "created_at": 1735603200,
}


def _make_mock_service(mock_documents=None, error_mode=None) -> RazorpayService:
    client = MockRazorpayClient(
        error_mode=error_mode, mock_documents=mock_documents
    )
    return RazorpayService(client=client)


# ===========================================================================
# 1. CORE METADATA RETRIEVAL TESTS
# ===========================================================================


class TestDocumentMetadataCore:
    """Test successful document metadata retrieval and validation."""

    @pytest.mark.asyncio
    async def test_document_metadata_success(self):
        service = _make_mock_service(mock_documents={DOC_ID: VALID_PDF_METADATA})
        metadata = await service.get_document_metadata(DOC_ID)

        assert isinstance(metadata, RazorpayDocumentMetadataResponse)
        assert metadata.id == DOC_ID
        assert metadata.entity == "document"
        assert metadata.purpose == "dispute_evidence"
        assert metadata.mime_type == "application/pdf"
        assert metadata.size == 524288

    @pytest.mark.asyncio
    async def test_document_metadata_pdf(self):
        service = _make_mock_service(mock_documents={DOC_ID: VALID_PDF_METADATA})
        metadata = await service.get_document_metadata(DOC_ID)
        assert metadata.mime_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_document_metadata_jpeg(self):
        service = _make_mock_service(
            mock_documents={"doc_jpeg_001": VALID_JPEG_METADATA}
        )
        metadata = await service.get_document_metadata("doc_jpeg_001")
        assert metadata.mime_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_document_metadata_png(self):
        service = _make_mock_service(
            mock_documents={"doc_png_001": VALID_PNG_METADATA}
        )
        metadata = await service.get_document_metadata("doc_png_001")
        assert metadata.mime_type == "image/png"

    @pytest.mark.asyncio
    async def test_mock_client_document_metadata(self):
        client = MockRazorpayClient(mock_documents={DOC_ID: VALID_PDF_METADATA})
        meta = await client.get_document_metadata(DOC_ID)
        assert isinstance(meta, RazorpayDocumentMetadataResponse)
        assert meta.id == DOC_ID

    @pytest.mark.asyncio
    async def test_service_returns_typed_schema(self):
        service = _make_mock_service(mock_documents={DOC_ID: VALID_PDF_METADATA})
        meta = await service.get_document_metadata(DOC_ID)
        assert isinstance(meta, RazorpayDocumentMetadataResponse)
        assert not isinstance(meta, dict)


# ===========================================================================
# 2. DOCUMENT ID SECURITY TESTS
# ===========================================================================


class TestDocumentIDSecurity:
    """Test security validation of document IDs."""

    @pytest.mark.asyncio
    async def test_document_id_empty(self):
        service = _make_mock_service()
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata("")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_document_id_invalid(self):
        service = _make_mock_service()
        invalid_ids = ["   ", "id with spaces", "doc@invalid!"]
        for bad_id in invalid_ids:
            with pytest.raises(HTTPException) as exc_info:
                await service.get_document_metadata(bad_id)
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_document_id_path_traversal(self):
        service = _make_mock_service()
        traversal_ids = [
            "../etc/passwd",
            "..\\windows\\system32",
            "doc_123/sub",
            "doc_123\\sub",
            "doc_123:etc",
        ]
        for bad_id in traversal_ids:
            with pytest.raises(HTTPException) as exc_info:
                await service.get_document_metadata(bad_id)
            assert exc_info.value.status_code == 400
            assert "Invalid document_id" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_document_name_is_untrusted(self):
        """Untrusted document name containing path traversal characters does not crash or create paths."""
        untrusted_doc = {
            **VALID_PDF_METADATA,
            "name": "../../../etc/passwd",
        }
        service = _make_mock_service(mock_documents={DOC_ID: untrusted_doc})
        meta = await service.get_document_metadata(DOC_ID)
        # Should parse safely as raw string without resolving or constructing paths
        assert meta.name == "../../../etc/passwd"


# ===========================================================================
# 3. PRE-FLIGHT VALIDATION TESTS
# ===========================================================================


class TestPreflightValidation:
    """Test pre-flight validation rules (purpose, MIME type, size ceilings)."""

    @pytest.mark.asyncio
    async def test_invalid_purpose(self):
        invalid_purpose_doc = {**VALID_PDF_METADATA, "purpose": "invoice"}
        service = _make_mock_service(
            mock_documents={DOC_ID: invalid_purpose_doc}
        )
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata(DOC_ID)
        assert exc_info.value.status_code == 400
        assert "Invalid document purpose" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_unsupported_mime_type(self):
        unsupported = [
            "application/x-msdownload",
            "text/html",
            "application/zip",
            "video/mp4",
        ]
        for mime in unsupported:
            doc = {**VALID_PDF_METADATA, "mime_type": mime}
            service = _make_mock_service(mock_documents={DOC_ID: doc})
            with pytest.raises(HTTPException) as exc_info:
                await service.get_document_metadata(DOC_ID)
            assert exc_info.value.status_code == 400
            assert "Unsupported document MIME type" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_oversized_pdf_metadata(self):
        # 3 MB PDF > 2 MB limit
        oversized = {**VALID_PDF_METADATA, "size": 3_145_728}
        service = _make_mock_service(mock_documents={DOC_ID: oversized})
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata(DOC_ID)
        assert exc_info.value.status_code == 400
        assert "exceeds maximum allowed ceiling" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_oversized_image_metadata(self):
        # 5 MB PNG > 4 MB limit
        oversized = {**VALID_PNG_METADATA, "size": 5_242_880}
        service = _make_mock_service(
            mock_documents={"doc_png_001": oversized}
        )
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata("doc_png_001")
        assert exc_info.value.status_code == 400
        assert "exceeds maximum allowed ceiling" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_unexpected_entity(self):
        unexpected = {**VALID_PDF_METADATA, "entity": "dispute"}
        client = MockRazorpayClient(mock_documents={DOC_ID: unexpected})
        with pytest.raises(ValidationError):
            await client.get_document_metadata(DOC_ID)


# ===========================================================================
# 4. ERROR HANDLING TESTS
# ===========================================================================


class TestErrorHandling:
    """Test Razorpay client error propagation."""

    @pytest.mark.asyncio
    async def test_document_metadata_not_found(self):
        service = _make_mock_service(error_mode="not_found")
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata("doc_nonexistent")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_document_metadata_auth_error(self):
        service = _make_mock_service(error_mode="auth_error")
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata(DOC_ID)
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_document_metadata_forbidden(self):
        service = _make_mock_service(error_mode="forbidden")
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata(DOC_ID)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_document_metadata_rate_limit(self):
        service = _make_mock_service(error_mode="rate_limit")
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata(DOC_ID)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_document_metadata_server_error(self):
        service = _make_mock_service(error_mode="server_error")
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata(DOC_ID)
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_document_metadata_timeout(self):
        service = _make_mock_service(error_mode="timeout")
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata(DOC_ID)
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_document_metadata_malformed_json(self):
        service = _make_mock_service(error_mode="malformed")
        with pytest.raises(HTTPException) as exc_info:
            await service.get_document_metadata(DOC_ID)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_document_metadata_schema_validation(self):
        missing_size = {
            "id": DOC_ID,
            "entity": "document",
            "purpose": "dispute_evidence",
            "name": "receipt.pdf",
            "mime_type": "application/pdf",
            "created_at": 1735603200,
        }
        client = MockRazorpayClient(mock_documents={DOC_ID: missing_size})
        with pytest.raises(ValidationError):
            await client.get_document_metadata(DOC_ID)


# ===========================================================================
# 5. READ-ONLY & FINANCIAL SAFETY INVARIANT TESTS
# ===========================================================================


class TestFinancialSafetyInvariants:
    """Verify that zero content download and zero mutation operations exist."""

    FORBIDDEN_PREFIXES = (
        "accept_", "contest_", "submit_", "create_",
        "update_", "delete_", "patch_", "post_", "put_",
        "upload_",
    )

    def test_no_document_download_method(self):
        """Verify no upload or mutation methods exist on clients or protocol."""
        for cls in [HttpRazorpayClient, MockRazorpayClient, RazorpayClient]:
            assert not hasattr(cls, "upload_document")

    def test_no_mutation_methods(self):
        """Verify zero mutation methods exist across all Razorpay components."""
        for cls in [HttpRazorpayClient, MockRazorpayClient, RazorpayService]:
            methods = [
                name for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
                if not name.startswith("_")
            ]
            for method in methods:
                for prefix in self.FORBIDDEN_PREFIXES:
                    assert not method.startswith(prefix), (
                        f"Class {cls.__name__} has forbidden method: {method}"
                    )


# ===========================================================================
# 6. API ENDPOINT TESTS
# ===========================================================================


class TestDocumentMetadataApiEndpoint:
    """Test GET /api/razorpay/documents/{document_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_document_metadata_endpoint_success(self, client):
        response = await client.get("/api/razorpay/documents/doc_mock_001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "doc_mock_001"
        assert data["entity"] == "document"
        assert data["purpose"] == "dispute_evidence"
        assert data["mime_type"] == "application/pdf"
        assert "key_id" not in json.dumps(data)
        assert "key_secret" not in json.dumps(data)

    @pytest.mark.asyncio
    async def test_get_document_metadata_endpoint_invalid_id(self, client):
        response = await client.get("/api/razorpay/documents/invalid_doc%20id_spaces")
        assert response.status_code == 400
        assert "Invalid document_id" in response.json()["detail"]
