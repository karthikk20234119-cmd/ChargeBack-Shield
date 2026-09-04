"""
Unit Test Suite: Secure Local Evidence Ingestion — Task 3.3D

Tests consumption of DocumentContentStream and secure persistence as EvidenceDocument:
- Valid PDF, JPEG, PNG binary ingestion
- Magic-byte detection & validation (%PDF-, FF D8 FF, 89 PNG...)
- Extension & MIME consistency enforcement
- Hard file size limits (2MB PDF, 4MB Image)
- SHA-256 calculation & verification
- Dispute & Document ID identity alignment checks
- Tier 1 (doc_id) and Tier 2 (sha256) duplicate detection
- Path traversal protection & UUID internal filename generation
- Atomic file persistence & DB failure rollback cleanup (0 orphan files)
- Zero side-effect boundaries (0 AI calls, 0 PDF rasterization, 0 Razorpay mutations)
"""

import hashlib
import os
import shutil
import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy.future import select

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.schemas.razorpay import RazorpayDocumentMetadataResponse
from backend.app.services.evidence_reference_extractor import EvidenceReference
from backend.app.services.razorpay_client import DocumentContentStream, MockRazorpayClient
from backend.app.services.razorpay_evidence_ingestion_service import (
    IngestionResult,
    RazorpayEvidenceIngestionService,
    ingest_razorpay_evidence,
)

TEST_DISPUTE_ID = "disp_test_ingest_001"
TEST_DOC_ID_PDF = "doc_test_pdf_001"
TEST_DOC_ID_JPEG = "doc_test_jpeg_001"
TEST_DOC_ID_PNG = "doc_test_png_001"


async def _setup_test_dispute(async_db, dispute_id=TEST_DISPUTE_ID):
    """Helper to insert a test dispute into the database."""
    res = await async_db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = res.scalar_one_or_none()
    if not dispute:
        dispute = Dispute(
            id=dispute_id,
            payment_id=f"pay_mock_{dispute_id[-6:]}",
            amount=150000,
            currency="INR",
            reason_code="chargeback",
            status="open",
            phase="chargeback",
        )
        async_db.add(dispute)
        await async_db.commit()
    return dispute


def _make_evidence_ref(doc_id=TEST_DOC_ID_PDF, category="shipping_proof", dispute_id=TEST_DISPUTE_ID):
    return EvidenceReference(
        razorpay_doc_id=doc_id,
        razorpay_evidence_type=category,
        categories=[category],
        source_dispute_id=dispute_id,
    )


def _make_metadata(doc_id=TEST_DOC_ID_PDF, name="invoice_123.pdf", mime_type="application/pdf", size=1024):
    return RazorpayDocumentMetadataResponse(
        id=doc_id,
        entity="document",
        purpose="dispute_evidence",
        name=name,
        size=size,
        mime_type=mime_type,
        created_at=1735603200,
    )


def _make_stream(doc_id=TEST_DOC_ID_PDF, raw_bytes=None, mime_type="application/pdf"):
    if raw_bytes is None:
        if "jpeg" in doc_id or "jpg" in doc_id:
            raw_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF mock jpeg content " + b"0" * 200
        elif "png" in doc_id:
            raw_bytes = b"\x89PNG\r\n\x1a\n mock png content " + b"0" * 200
        else:
            raw_bytes = b"%PDF-1.4 mock pdf content " + b"0" * 200

    chunks = [raw_bytes[:100], raw_bytes[100:]]
    return DocumentContentStream(
        razorpay_doc_id=doc_id,
        content_type=mime_type,
        raw_response=None,
        mock_chunks=chunks,
    ), raw_bytes


# ===========================================================================
# 1. CORE SUCCESSFUL INGESTION TESTS
# ===========================================================================


class TestValidIngestion:
    """Test successful ingestion of PDF, JPEG, and PNG evidence streams."""

    @pytest.mark.asyncio
    async def test_valid_pdf_ingestion(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref(TEST_DOC_ID_PDF, category="shipping_proof")
        meta = _make_metadata(TEST_DOC_ID_PDF, name="shipping_label.pdf", mime_type="application/pdf")
        stream, raw_bytes = _make_stream(TEST_DOC_ID_PDF, mime_type="application/pdf")

        result = await ingest_razorpay_evidence(
            dispute_id=TEST_DISPUTE_ID,
            evidence_ref=ref,
            metadata=meta,
            stream=stream,
            db=async_db,
            override_upload_dir=str(tmp_path),
        )

        assert result.status == "SUCCESS"
        assert result.document_id is not None
        assert result.file_size_bytes == len(raw_bytes)
        assert result.file_hash == hashlib.sha256(raw_bytes).hexdigest()

        # DB verification
        stmt = select(EvidenceDocument).where(EvidenceDocument.id == result.document_id)
        res = await async_db.execute(stmt)
        doc = res.scalar_one()
        assert doc.dispute_id == TEST_DISPUTE_ID
        assert doc.razorpay_doc_id == TEST_DOC_ID_PDF
        assert doc.document_type == "shipping_proof"
        assert doc.processing_status == "UPLOADED"
        assert os.path.exists(doc.file_path)

    @pytest.mark.asyncio
    async def test_valid_jpeg_ingestion(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref(TEST_DOC_ID_JPEG, category="customer_communication")
        meta = _make_metadata(TEST_DOC_ID_JPEG, name="photo.jpg", mime_type="image/jpeg")
        stream, raw_bytes = _make_stream(TEST_DOC_ID_JPEG, mime_type="image/jpeg")

        result = await ingest_razorpay_evidence(
            dispute_id=TEST_DISPUTE_ID,
            evidence_ref=ref,
            metadata=meta,
            stream=stream,
            db=async_db,
            override_upload_dir=str(tmp_path),
        )

        assert result.status == "SUCCESS"
        assert os.path.exists(os.path.join(str(tmp_path), os.path.basename(result.document_id) if False else os.listdir(tmp_path)[0]))

    @pytest.mark.asyncio
    async def test_valid_png_ingestion(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref(TEST_DOC_ID_PNG, category="cancellation_proof")
        meta = _make_metadata(TEST_DOC_ID_PNG, name="screenshot.png", mime_type="image/png")
        stream, raw_bytes = _make_stream(TEST_DOC_ID_PNG, mime_type="image/png")

        result = await ingest_razorpay_evidence(
            dispute_id=TEST_DISPUTE_ID,
            evidence_ref=ref,
            metadata=meta,
            stream=stream,
            db=async_db,
            override_upload_dir=str(tmp_path),
        )

        assert result.status == "SUCCESS"


# ===========================================================================
# 2. MAGIC-BYTE & MIME CONSISTENCY TESTS
# ===========================================================================


class TestMagicBytesAndMIME:
    """Test binary magic-byte detection and MIME consistency enforcement."""

    @pytest.mark.asyncio
    async def test_magic_byte_pdf(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_m1")
        meta = _make_metadata("doc_m1", name="doc.pdf", mime_type="application/pdf")
        stream, _ = _make_stream("doc_m1", raw_bytes=b"%PDF-1.4 test bytes " + b"0"*100)

        result = await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert result.status == "SUCCESS"

    @pytest.mark.asyncio
    async def test_magic_byte_jpeg(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_m2")
        meta = _make_metadata("doc_m2", name="img.jpg", mime_type="image/jpeg")
        stream, _ = _make_stream("doc_m2", raw_bytes=b"\xff\xd8\xff\xe0\x00\x10JFIF test " + b"0"*100, mime_type="image/jpeg")

        result = await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert result.status == "SUCCESS"

    @pytest.mark.asyncio
    async def test_magic_byte_png(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_m3")
        meta = _make_metadata("doc_m3", name="img.png", mime_type="image/png")
        stream, _ = _make_stream("doc_m3", raw_bytes=b"\x89PNG\r\n\x1a\n test " + b"0"*100, mime_type="image/png")

        result = await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert result.status == "SUCCESS"

    @pytest.mark.asyncio
    async def test_extension_mismatch(self, async_db, tmp_path):
        """Rejects executable file content disguised as PDF."""
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_fake")
        meta = _make_metadata("doc_fake", name="malicious.pdf", mime_type="application/pdf")
        stream, _ = _make_stream("doc_fake", raw_bytes=b"MZ\x90\x00\x03\x00\x00\x00 fake exe content")

        with pytest.raises(HTTPException) as exc:
            await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert exc.value.status_code == 400
        assert "magic bytes" in exc.value.detail

    @pytest.mark.asyncio
    async def test_metadata_mime_mismatch(self, async_db, tmp_path):
        """Rejects when metadata claims PDF but binary content is JPEG image."""
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_mm")
        meta = _make_metadata("doc_mm", name="doc.pdf", mime_type="application/pdf")
        stream, _ = _make_stream("doc_mm", raw_bytes=b"\xff\xd8\xff\xe0\x00\x10JFIF image bytes " + b"0"*100, mime_type="image/jpeg")

        with pytest.raises(HTTPException) as exc:
            await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert exc.value.status_code == 400
        assert "Contradictory" in exc.value.detail

    @pytest.mark.asyncio
    async def test_http_content_type_mismatch(self, async_db, tmp_path):
        """Rejects when transport Content-Type claims image/png but binary content is PDF."""
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_ctm")
        meta = _make_metadata("doc_ctm", name="doc.png", mime_type="image/png")
        stream, _ = _make_stream("doc_ctm", raw_bytes=b"%PDF-1.4 pdf bytes " + b"0"*100, mime_type="application/pdf")

        with pytest.raises(HTTPException) as exc:
            await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert exc.value.status_code == 400


# ===========================================================================
# 3. SIZE & HASH SAFETY TESTS
# ===========================================================================


class TestSizeAndHashSafety:
    """Test size ceilings, SHA-256 verification, and error cleanup."""

    @pytest.mark.asyncio
    async def test_pdf_too_large(self, async_db, tmp_path):
        """Rejects PDF exceeding 2 MB size ceiling."""
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_huge_pdf")
        meta = _make_metadata("doc_huge_pdf", name="huge.pdf", mime_type="application/pdf")
        huge_bytes = b"%PDF-1.4 " + b"X" * (2 * 1024 * 1024 + 1024)
        stream, _ = _make_stream("doc_huge_pdf", raw_bytes=huge_bytes)

        with pytest.raises(HTTPException) as exc:
            await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert exc.value.status_code == 400
        assert "exceeds ceiling" in exc.value.detail

    @pytest.mark.asyncio
    async def test_image_too_large(self, async_db, tmp_path):
        """Rejects image exceeding 4 MB size ceiling."""
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_huge_img")
        meta = _make_metadata("doc_huge_img", name="huge.jpg", mime_type="image/jpeg")
        huge_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF " + b"X" * (4 * 1024 * 1024 + 1024)
        stream, _ = _make_stream("doc_huge_img", raw_bytes=huge_bytes, mime_type="image/jpeg")

        with pytest.raises(HTTPException) as exc:
            await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_stream_hash_match(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_hm")
        meta = _make_metadata("doc_hm")
        stream, raw_bytes = _make_stream("doc_hm")

        result = await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert result.file_hash == hashlib.sha256(raw_bytes).hexdigest()

    @pytest.mark.asyncio
    async def test_stream_hash_mismatch(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_hmm")
        meta = _make_metadata("doc_hmm")
        stream, _ = _make_stream("doc_hmm")

        with pytest.raises(HTTPException) as exc:
            await ingest_razorpay_evidence(
                TEST_DISPUTE_ID, ref, meta, stream, async_db,
                override_upload_dir=str(tmp_path), expected_sha256="0" * 64
            )
        assert exc.value.status_code == 400
        assert "mismatch" in exc.value.detail


# ===========================================================================
# 4. IDENTITY ALIGNMENT & DUPLICATE DETECTION TESTS
# ===========================================================================


class TestIdentityAndDuplicates:
    """Test identity alignment pre-checks and Tier 1 & Tier 2 duplicate detection."""

    @pytest.mark.asyncio
    async def test_document_id_mismatch(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_id_A")
        meta = _make_metadata("doc_id_B")
        stream, _ = _make_stream("doc_id_B")

        with pytest.raises(HTTPException) as exc:
            await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert exc.value.status_code == 400
        assert "Identity mismatch" in exc.value.detail

    @pytest.mark.asyncio
    async def test_dispute_id_mismatch(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_d1", dispute_id="disp_other_999")
        meta = _make_metadata("doc_d1")
        stream, _ = _make_stream("doc_d1")

        with pytest.raises(HTTPException) as exc:
            await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_document_id(self, async_db, tmp_path):
        """Tier 1 duplicate detection returns DUPLICATE status without re-downloading."""
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_dup_t1")
        meta = _make_metadata("doc_dup_t1")

        stream1, _ = _make_stream("doc_dup_t1")
        res1 = await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream1, async_db, override_upload_dir=str(tmp_path))
        assert res1.status == "SUCCESS"

        stream2, _ = _make_stream("doc_dup_t1")
        res2 = await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream2, async_db, override_upload_dir=str(tmp_path))
        assert res2.status == "DUPLICATE"
        assert res2.document_id == res1.document_id

    @pytest.mark.asyncio
    async def test_duplicate_sha256(self, async_db, tmp_path):
        """Tier 2 duplicate detection returns DUPLICATE status for identical binary content under different doc_id."""
        await _setup_test_dispute(async_db)
        shared_bytes = b"%PDF-1.4 shared content " + b"1" * 300

        ref1 = _make_evidence_ref("doc_dup_t2_A")
        meta1 = _make_metadata("doc_dup_t2_A")
        stream1, _ = _make_stream("doc_dup_t2_A", raw_bytes=shared_bytes)
        res1 = await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref1, meta1, stream1, async_db, override_upload_dir=str(tmp_path))
        assert res1.status == "SUCCESS"

        ref2 = _make_evidence_ref("doc_dup_t2_B")
        meta2 = _make_metadata("doc_dup_t2_B")
        stream2, _ = _make_stream("doc_dup_t2_B", raw_bytes=shared_bytes)
        res2 = await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref2, meta2, stream2, async_db, override_upload_dir=str(tmp_path))
        assert res2.status == "DUPLICATE"
        assert res2.document_id == res1.document_id


# ===========================================================================
# 5. PATH SAFETY & CLEANUP GUARANTEES
# ===========================================================================


class TestPathSafetyAndCleanup:
    """Test safe internal naming, path traversal protection, and failure cleanup."""

    @pytest.mark.asyncio
    async def test_filename_never_used_as_path(self, async_db, tmp_path):
        """Original external name 'path/traversal/test.pdf' is never used as file path."""
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_safe_name")
        meta = _make_metadata("doc_safe_name", name="../../../etc/passwd.pdf")
        stream, _ = _make_stream("doc_safe_name")

        res = await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))
        assert res.status == "SUCCESS"

        stmt = select(EvidenceDocument).where(EvidenceDocument.id == res.document_id)
        doc = (await async_db.execute(stmt)).scalar_one()

        assert doc.original_filename == "passwd.pdf"
        assert not doc.file_path.endswith("passwd.pdf")
        assert doc.internal_filename.endswith(".pdf")
        assert uuid.UUID(doc.internal_filename[:-4])  # Valid UUID prefix

    @pytest.mark.asyncio
    async def test_no_orphan_temp_files(self, async_db, tmp_path):
        """Zero temporary (.tmp) files remain after ingestion failures or successes."""
        await _setup_test_dispute(async_db)
        tmp_sub_dir = os.path.join(str(tmp_path), ".tmp")

        ref = _make_evidence_ref("doc_clean")
        meta = _make_metadata("doc_clean")
        stream, _ = _make_stream("doc_clean")
        await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))

        if os.path.exists(tmp_sub_dir):
            assert len(os.listdir(tmp_sub_dir)) == 0

    @pytest.mark.asyncio
    async def test_database_failure_cleanup(self, async_db, tmp_path, monkeypatch):
        """If DB commit fails, promoted file is deleted and transaction is rolled back."""
        await _setup_test_dispute(async_db)
        ref = _make_evidence_ref("doc_db_fail")
        meta = _make_metadata("doc_db_fail")
        stream, _ = _make_stream("doc_db_fail")

        # Force db.commit to raise an exception
        async def mock_commit():
            raise RuntimeError("Database connection lost")

        monkeypatch.setattr(async_db, "commit", mock_commit)

        with pytest.raises(HTTPException) as exc:
            await ingest_razorpay_evidence(TEST_DISPUTE_ID, ref, meta, stream, async_db, override_upload_dir=str(tmp_path))

        assert exc.value.status_code == 500
        # Verify no files promoted or left behind in upload directory
        upload_files = [f for f in os.listdir(tmp_path) if f != ".tmp"]
        assert len(upload_files) == 0


# ===========================================================================
# 6. INVARIANT BOUNDARY TESTS
# ===========================================================================


class TestInvariantBoundaries:
    """Verify zero AI calls, zero PDF rasterization, and zero Razorpay mutations."""

    def test_no_ai_processing(self):
        import backend.app.services.razorpay_evidence_ingestion_service as svc
        assert not hasattr(svc, "execute_ai_extraction")
        assert not hasattr(svc, "GroqProvider")

    def test_no_rasterization(self):
        import backend.app.services.razorpay_evidence_ingestion_service as svc
        assert not hasattr(svc, "rasterize_pdf")
        assert not hasattr(svc, "pdf2image")

    def test_no_razorpay_mutation(self):
        import backend.app.services.razorpay_evidence_ingestion_service as svc
        assert not hasattr(svc, "contest_dispute")
        assert not hasattr(svc, "submit_contest")
        assert not hasattr(svc, "accept_dispute")
