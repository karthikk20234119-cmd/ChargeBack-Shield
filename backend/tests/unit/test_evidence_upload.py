import os
import pytest
from unittest.mock import patch
from sqlalchemy.future import select
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument

# Helper sample file bytes with valid magic headers
VALID_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xd9"
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
MALICIOUS_EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00 This program cannot be run in DOS mode."

async def create_test_dispute(async_db, dispute_id: str = "disp_upload_test_001"):
    dispute = Dispute(
        id=dispute_id,
        payment_id="pay_test_upload",
        amount=500000,
        currency="INR",
        reason_code="13.1",
        status="open"
    )
    async_db.add(dispute)
    await async_db.commit()
    return dispute

@pytest.mark.asyncio
async def test_upload_valid_pdf(client, async_db, tmp_path):
    await create_test_dispute(async_db, "disp_pdf")
    upload_dir = str(tmp_path / "uploads")
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        files = {"file": ("invoice.pdf", VALID_PDF_BYTES, "application/pdf")}
        res = await client.post("/api/disputes/disp_pdf/evidence", files=files)
        
        assert res.status_code == 201
        data = res.json()
        assert data["dispute_id"] == "disp_pdf"
        assert data["filename"] == "invoice.pdf"
        assert data["mime_type"] == "application/pdf"
        assert data["status"] == "UPLOADED"
        assert len(data["sha256"]) == 64

        # Verify DB record
        doc_stmt = select(EvidenceDocument).where(EvidenceDocument.id == data["evidence_id"])
        doc_res = await async_db.execute(doc_stmt)
        doc = doc_res.scalar_one_or_none()
        assert doc is not None
        assert doc.original_filename == "invoice.pdf"
        assert os.path.exists(doc.file_path)

@pytest.mark.asyncio
async def test_upload_valid_jpeg(client, async_db, tmp_path):
    await create_test_dispute(async_db, "disp_jpeg")
    upload_dir = str(tmp_path / "uploads")
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        files = {"file": ("receipt.jpg", VALID_JPEG_BYTES, "image/jpeg")}
        res = await client.post("/api/disputes/disp_jpeg/evidence", files=files)
        
        assert res.status_code == 201
        data = res.json()
        assert data["mime_type"] == "image/jpeg"
        assert data["filename"] == "receipt.jpg"

@pytest.mark.asyncio
async def test_upload_valid_png(client, async_db, tmp_path):
    await create_test_dispute(async_db, "disp_png")
    upload_dir = str(tmp_path / "uploads")
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        files = {"file": ("signature.png", VALID_PNG_BYTES, "image/png")}
        res = await client.post("/api/disputes/disp_png/evidence", files=files)
        
        assert res.status_code == 201
        data = res.json()
        assert data["mime_type"] == "image/png"
        assert data["filename"] == "signature.png"

@pytest.mark.asyncio
async def test_upload_missing_dispute(client, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        files = {"file": ("invoice.pdf", VALID_PDF_BYTES, "application/pdf")}
        res = await client.post("/api/disputes/nonexistent_dispute_id/evidence", files=files)
        assert res.status_code == 404
        assert "not found" in res.json()["detail"]

@pytest.mark.asyncio
async def test_upload_empty_file(client, async_db, tmp_path):
    await create_test_dispute(async_db, "disp_empty")
    upload_dir = str(tmp_path / "uploads")
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        files = {"file": ("empty.pdf", b"", "application/pdf")}
        res = await client.post("/api/disputes/disp_empty/evidence", files=files)
        assert res.status_code == 400
        assert "empty" in res.json()["detail"]

@pytest.mark.asyncio
async def test_upload_invalid_extension(client, async_db, tmp_path):
    await create_test_dispute(async_db, "disp_ext")
    upload_dir = str(tmp_path / "uploads")
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        files = {"file": ("document.docx", b"dummy content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        res = await client.post("/api/disputes/disp_ext/evidence", files=files)
        assert res.status_code == 400
        assert "Unsupported file extension" in res.json()["detail"]

@pytest.mark.asyncio
async def test_upload_invalid_mime_magic_bytes(client, async_db, tmp_path):
    """Security test: malicious.exe renamed to evidence.pdf must be rejected due to magic byte mismatch."""
    await create_test_dispute(async_db, "disp_spoof")
    upload_dir = str(tmp_path / "uploads")
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        files = {"file": ("evidence.pdf", MALICIOUS_EXE_BYTES, "application/pdf")}
        res = await client.post("/api/disputes/disp_spoof/evidence", files=files)
        assert res.status_code == 400
        assert "magic bytes do not match" in res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_upload_oversized_pdf(client, async_db, tmp_path):
    await create_test_dispute(async_db, "disp_big_pdf")
    upload_dir = str(tmp_path / "uploads")
    
    # Generate fake oversized PDF > 2MB (e.g. 2.1 MB)
    big_pdf_bytes = VALID_PDF_BYTES + (b"0" * (2 * 1024 * 1024 + 500))
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        files = {"file": ("big.pdf", big_pdf_bytes, "application/pdf")}
        res = await client.post("/api/disputes/disp_big_pdf/evidence", files=files)
        assert res.status_code == 400
        assert "exceeds maximum limit" in res.json()["detail"]

@pytest.mark.asyncio
async def test_upload_oversized_image(client, async_db, tmp_path):
    await create_test_dispute(async_db, "disp_big_img")
    upload_dir = str(tmp_path / "uploads")
    
    # Generate fake oversized PNG > 4MB (e.g. 4.1 MB)
    big_png_bytes = VALID_PNG_BYTES + (b"0" * (4 * 1024 * 1024 + 500))
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        files = {"file": ("big.png", big_png_bytes, "image/png")}
        res = await client.post("/api/disputes/disp_big_img/evidence", files=files)
        assert res.status_code == 400
        assert "exceeds maximum limit" in res.json()["detail"]

@pytest.mark.asyncio
async def test_upload_duplicate_sha256(client, async_db, tmp_path):
    await create_test_dispute(async_db, "disp_dup")
    upload_dir = str(tmp_path / "uploads")
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        files = {"file": ("invoice1.pdf", VALID_PDF_BYTES, "application/pdf")}
        
        # First Upload -> 201 Created
        res1 = await client.post("/api/disputes/disp_dup/evidence", files=files)
        assert res1.status_code == 201
        
        # Second Upload (Exact same content/hash) -> 409 Conflict
        files2 = {"file": ("invoice2_rename.pdf", VALID_PDF_BYTES, "application/pdf")}
        res2 = await client.post("/api/disputes/disp_dup/evidence", files=files2)
        assert res2.status_code == 409
        assert "already been uploaded" in res2.json()["detail"]

@pytest.mark.asyncio
async def test_upload_path_traversal_filename(client, async_db, tmp_path):
    """Security test: ../../../../important.txt and ..\..\..\important.txt must be sanitized safely."""
    await create_test_dispute(async_db, "disp_traversal")
    upload_dir = str(tmp_path / "uploads")
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        # 1. Unix traversal
        files1 = {"file": ("../../../../important.pdf", VALID_PDF_BYTES, "application/pdf")}
        res1 = await client.post("/api/disputes/disp_traversal/evidence", files=files1)
        assert res1.status_code == 201
        data1 = res1.json()
        assert data1["filename"] == "important.pdf"

        # 2. Windows traversal
        files2 = {"file": ("..\\..\\..\\secret.png", VALID_PNG_BYTES, "image/png")}
        res2 = await client.post("/api/disputes/disp_traversal/evidence", files=files2)
        assert res2.status_code == 201
        data2 = res2.json()
        assert data2["filename"] == "secret.png"

        # Verify that all stored files remain strictly inside upload_dir
        for file_item in os.listdir(upload_dir):
            full_item_path = os.path.join(upload_dir, file_item)
            assert os.path.abspath(full_item_path).startswith(os.path.abspath(upload_dir))

@pytest.mark.asyncio
async def test_upload_storage_failure(client, async_db, tmp_path):
    await create_test_dispute(async_db, "disp_store_fail")
    upload_dir = str(tmp_path / "uploads")
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        with patch("builtins.open", side_effect=IOError("Disk permission error")):
            files = {"file": ("invoice.pdf", VALID_PDF_BYTES, "application/pdf")}
            res = await client.post("/api/disputes/disp_store_fail/evidence", files=files)
            assert res.status_code == 500
            assert "Failed to write evidence file" in res.json()["detail"]

@pytest.mark.asyncio
async def test_upload_database_failure(client, async_db, tmp_path):
    await create_test_dispute(async_db, "disp_db_fail")
    upload_dir = str(tmp_path / "uploads")
    
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir):
        with patch.object(async_db, "commit", side_effect=Exception("Database connection lost")):
            files = {"file": ("invoice.pdf", VALID_PDF_BYTES, "application/pdf")}
            res = await client.post("/api/disputes/disp_db_fail/evidence", files=files)
            assert res.status_code == 500
            assert "Failed to record evidence document" in res.json()["detail"]
