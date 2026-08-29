import os
import io
import pytest
from unittest.mock import patch
from PIL import Image
from reportlab.pdfgen import canvas
from sqlalchemy.future import select

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.models.processed_artifact import ProcessedArtifact
from backend.app.utils.file_processor import calculate_sha256

def generate_pdf_bytes(num_pages: int = 1) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for p in range(1, num_pages + 1):
        c.drawString(100, 750, f"Synthetic Test PDF Page {p}")
        c.showPage()
    c.save()
    return buf.getvalue()

def generate_png_bytes(width: int = 100, height: int = 100, color: str = "red") -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()

def generate_jpeg_bytes(width: int = 100, height: int = 100, color: str = "blue") -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="JPEG")
    return buf.getvalue()

async def create_test_dispute_and_doc(async_db, dispute_id: str, doc_id: str, file_name: str, file_bytes: bytes, tmp_upload_dir: str):
    os.makedirs(tmp_upload_dir, exist_ok=True)
    file_path = os.path.join(tmp_upload_dir, f"{doc_id}_{file_name}")
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    sha256 = calculate_sha256(file_bytes)
    
    # Dispute
    stmt = select(Dispute).where(Dispute.id == dispute_id)
    res = await async_db.execute(stmt)
    dispute = res.scalar_one_or_none()
    if not dispute:
        dispute = Dispute(id=dispute_id, payment_id="pay_test", amount=500000, reason_code="13.1", status="open")
        async_db.add(dispute)
        
    doc = EvidenceDocument(
        id=doc_id,
        dispute_id=dispute_id,
        original_filename=file_name,
        internal_filename=f"{doc_id}_{file_name}",
        file_path=file_path,
        file_hash=sha256,
        file_size_bytes=len(file_bytes),
        mime_type="application/pdf" if file_name.endswith(".pdf") else "image/png",
        processing_status="UPLOADED"
    )
    async_db.add(doc)
    await async_db.commit()
    return doc

# ------------------------------------------------------------------
# Image Processing Tests
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_valid_png(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    png_bytes = generate_png_bytes(200, 200)
    doc = await create_test_dispute_and_doc(async_db, "disp_img_1", "doc_png_1", "test.png", png_bytes, upload_dir)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "READY_FOR_AI"
        assert data["number_of_pages"] == 1
        assert len(data["processed_artifacts"]) == 1

        page_file = os.path.join(processed_dir, doc.id, "page_001.png")
        assert os.path.exists(page_file)

@pytest.mark.asyncio
async def test_process_valid_jpeg(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    jpeg_bytes = generate_jpeg_bytes(300, 300)
    doc = await create_test_dispute_and_doc(async_db, "disp_img_2", "doc_jpeg_1", "test.jpg", jpeg_bytes, upload_dir)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "READY_FOR_AI"

@pytest.mark.asyncio
async def test_process_corrupted_image(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    corrupt_bytes = b"\x89PNG\r\n\x1a\n" + b"bad_corrupted_payload_bytes"
    doc = await create_test_dispute_and_doc(async_db, "disp_img_3", "doc_corrupt_img", "bad.png", corrupt_bytes, upload_dir)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 400
        assert "Corrupted, invalid, or unsafe image" in res.json()["detail"]

        # Check DB status is PROCESSING_FAILED
        doc_stmt = select(EvidenceDocument).where(EvidenceDocument.id == doc.id)
        doc_res = await async_db.execute(doc_stmt)
        assert doc_res.scalar_one().processing_status == "PROCESSING_FAILED"

@pytest.mark.asyncio
async def test_process_unsafe_large_image(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    png_bytes = generate_png_bytes(50, 50)
    doc = await create_test_dispute_and_doc(async_db, "disp_img_4", "doc_huge_img", "huge.png", png_bytes, upload_dir)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir), \
         patch("backend.app.config.settings.MAX_IMAGE_PIXELS", 100):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 400
        assert "exceed maximum safety pixel limit" in res.json()["detail"]

# ------------------------------------------------------------------
# PDF Processing Tests
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_valid_single_page_pdf(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    pdf_bytes = generate_pdf_bytes(1)
    doc = await create_test_dispute_and_doc(async_db, "disp_pdf_1", "doc_pdf_single", "single.pdf", pdf_bytes, upload_dir)

    mock_pil = Image.new("RGB", (600, 800), "white")
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir), \
         patch("backend.app.services.processing_service.convert_from_bytes", return_value=[mock_pil]):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "READY_FOR_AI"
        assert data["number_of_pages"] == 1

@pytest.mark.asyncio
async def test_process_valid_multi_page_pdf(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    pdf_bytes = generate_pdf_bytes(3)
    doc = await create_test_dispute_and_doc(async_db, "disp_pdf_2", "doc_pdf_multi", "multi.pdf", pdf_bytes, upload_dir)

    mock_pil_pages = [Image.new("RGB", (600, 800), "white") for _ in range(3)]
    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir), \
         patch("backend.app.services.processing_service.convert_from_bytes", return_value=mock_pil_pages):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "READY_FOR_AI"
        assert data["number_of_pages"] == 3

        # Confirm all page files exist
        assert os.path.exists(os.path.join(processed_dir, doc.id, "page_001.png"))
        assert os.path.exists(os.path.join(processed_dir, doc.id, "page_002.png"))
        assert os.path.exists(os.path.join(processed_dir, doc.id, "page_003.png"))

@pytest.mark.asyncio
async def test_process_corrupted_pdf(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    corrupt_pdf_bytes = b"%PDF-1.4\ncorrupted_pdf_stream_garbage"
    doc = await create_test_dispute_and_doc(async_db, "disp_pdf_3", "doc_pdf_corrupt", "corrupt.pdf", corrupt_pdf_bytes, upload_dir)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 400
        assert "Corrupted or unparseable PDF" in res.json()["detail"]

@pytest.mark.asyncio
async def test_process_excessive_page_pdf(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    pdf_bytes = generate_pdf_bytes(12)
    doc = await create_test_dispute_and_doc(async_db, "disp_pdf_4", "doc_pdf_excessive", "excessive.pdf", pdf_bytes, upload_dir)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir), \
         patch("backend.app.config.settings.MAX_PDF_PAGES", 10):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 400
        assert "exceeds maximum allowed limit of 10 pages" in res.json()["detail"]

@pytest.mark.asyncio
async def test_process_missing_pdf_file(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    pdf_bytes = generate_pdf_bytes(1)
    doc = await create_test_dispute_and_doc(async_db, "disp_pdf_5", "doc_pdf_missing", "missing.pdf", pdf_bytes, upload_dir)

    # Delete source file from storage
    os.remove(doc.file_path)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 400
        assert "missing from storage" in res.json()["detail"]

@pytest.mark.asyncio
async def test_process_pdf_sha256_mismatch(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    pdf_bytes = generate_pdf_bytes(1)
    doc = await create_test_dispute_and_doc(async_db, "disp_pdf_6", "doc_pdf_tampered", "tampered.pdf", pdf_bytes, upload_dir)

    # Tamper with file content on disk
    with open(doc.file_path, "wb") as f:
        f.write(pdf_bytes + b"tampered_extra_bytes")

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 400
        assert "hash mismatch" in res.json()["detail"].lower()

# ------------------------------------------------------------------
# Security & State Tests
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_source_path_outside_upload_directory(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    outside_dir = str(tmp_path / "outside")
    processed_dir = str(tmp_path / "processed")
    
    png_bytes = generate_png_bytes()
    doc = await create_test_dispute_and_doc(async_db, "disp_sec_1", "doc_outside", "outside.png", png_bytes, outside_dir)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 400
        assert "outside allowed upload directory" in res.json()["detail"]

@pytest.mark.asyncio
async def test_processed_output_stays_inside_directory(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    png_bytes = generate_png_bytes()
    doc = await create_test_dispute_and_doc(async_db, "disp_sec_2", "doc_safe_path", "safe.png", png_bytes, upload_dir)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir):
        
        res = await client.post(f"/api/evidence/{doc.id}/process")
        assert res.status_code == 200

        # Verify all output files are contained in processed_dir
        for root, dirs, files in os.walk(processed_dir):
            for file_name in files:
                full_path = os.path.abspath(os.path.join(root, file_name))
                assert full_path.startswith(os.path.abspath(processed_dir))

@pytest.mark.asyncio
async def test_processing_idempotency(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    png_bytes = generate_png_bytes()
    doc = await create_test_dispute_and_doc(async_db, "disp_idem", "doc_idem", "idem.png", png_bytes, upload_dir)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir):
        
        # 1. First process -> 200 READY_FOR_AI
        res1 = await client.post(f"/api/evidence/{doc.id}/process")
        assert res1.status_code == 200
        assert res1.json()["status"] == "READY_FOR_AI"

        # 2. Second process -> Returns idempotent existing result
        res2 = await client.post(f"/api/evidence/{doc.id}/process")
        assert res2.status_code == 200
        assert res2.json()["status"] == "READY_FOR_AI"

@pytest.mark.asyncio
async def test_failed_processing_can_retry(client, async_db, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    
    # Start with corrupted content
    corrupt_bytes = b"\x89PNG\r\n\x1a\ncorrupt"
    doc = await create_test_dispute_and_doc(async_db, "disp_retry", "doc_retry", "retry.png", corrupt_bytes, upload_dir)

    with patch("backend.app.config.settings.UPLOAD_DIR", upload_dir), \
         patch("backend.app.config.settings.PROCESSED_DIR", processed_dir):
        
        # 1. First processing fails -> PROCESSING_FAILED
        res1 = await client.post(f"/api/evidence/{doc.id}/process")
        assert res1.status_code == 400

        # Fix file content on disk and update DB file_hash to simulate re-upload/fix
        valid_png = generate_png_bytes()
        with open(doc.file_path, "wb") as f:
            f.write(valid_png)
        doc.file_hash = calculate_sha256(valid_png)
        await async_db.commit()

        # 2. Second process retry -> Success READY_FOR_AI
        res2 = await client.post(f"/api/evidence/{doc.id}/process")
        assert res2.status_code == 200
        assert res2.json()["status"] == "READY_FOR_AI"
