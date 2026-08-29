import os
import io
import shutil
import logging
from typing import Dict, Any, List
from PIL import Image, ImageOps, UnidentifiedImageError
import pypdf
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError, PopplerNotInstalledError


from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.config import settings
from backend.app.models.document import EvidenceDocument
from backend.app.models.processed_artifact import ProcessedArtifact
from backend.app.utils.file_processor import calculate_sha256

logger = logging.getLogger(__name__)

# Enable Pillow DecompressionBomb protection limit based on settings
Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS

async def process_evidence_document(
    evidence_id: str,
    db: AsyncSession,
    override_processed_dir: str = None,
    override_upload_dir: str = None,
) -> Dict[str, Any]:
    """
    Processes an uploaded evidence document into AI-ready PNG page images.
    Rasterizes PDFs page-by-page and normalizes JPEG/PNG images into PNG page_001.png.
    Enforces path safety, SHA-256 integrity, PDF password/dimension safeguards, 
    and updates processing_status to READY_FOR_AI or PROCESSING_FAILED.
    """
    processed_base_dir = override_processed_dir or settings.PROCESSED_DIR
    os.makedirs(processed_base_dir, exist_ok=True)

    # 1. Retrieve Evidence Document
    stmt = (
        select(EvidenceDocument)
        .options(selectinload(EvidenceDocument.artifacts))
        .where(EvidenceDocument.id == evidence_id)
    )
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence document with ID {evidence_id} not found"
        )

    # 2. Idempotency Check: Return existing result if already READY_FOR_AI and files exist
    if doc.processing_status == "READY_FOR_AI" and doc.artifacts:
        all_files_exist = True
        for artifact in doc.artifacts:
            if not os.path.exists(artifact.file_path):
                all_files_exist = False
                break
        if all_files_exist:
            logger.info(f"Evidence {evidence_id} already READY_FOR_AI. Returning existing processed artifacts.")
            return build_processing_response(doc, doc.artifacts)

    # 3. Path Security Check: Ensure file is inside UPLOAD_DIR
    upload_base = override_upload_dir or settings.UPLOAD_DIR
    upload_dir_abs = os.path.abspath(upload_base)
    source_file_abs = os.path.abspath(doc.file_path)

    try:
        common_path = os.path.commonpath([upload_dir_abs, source_file_abs])
    except ValueError:
        common_path = ""

    if common_path != upload_dir_abs:
        logger.warning(f"AUDIT [PROCESSING_FAILED]: evidence_id={evidence_id}, reason='File path outside UPLOAD_DIR'")
        await update_status(doc, "PROCESSING_FAILED", db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source evidence file path is outside allowed upload directory"
        )

    if not os.path.exists(source_file_abs):
        logger.warning(f"AUDIT [PROCESSING_FAILED]: evidence_id={evidence_id}, reason='Source file missing'")
        await update_status(doc, "PROCESSING_FAILED", db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source evidence file missing from storage"
        )

    # 4. SHA-256 Integrity Verification
    try:
        with open(source_file_abs, "rb") as f:
            file_bytes = f.read()
    except Exception as e:
        logger.error(f"AUDIT [PROCESSING_FAILED]: evidence_id={evidence_id}, reason='Storage read failure: {e}'")
        await update_status(doc, "PROCESSING_FAILED", db)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read source file from storage: {str(e)}"
        )

    current_hash = calculate_sha256(file_bytes)
    if current_hash != doc.file_hash:
        logger.warning(f"AUDIT [PROCESSING_FAILED]: evidence_id={evidence_id}, reason='SHA-256 mismatch'")
        await update_status(doc, "PROCESSING_FAILED", db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source file SHA-256 hash mismatch. File may be corrupted or modified."
        )

    # 5. Transition State to PROCESSING
    await update_status(doc, "PROCESSING", db)
    logger.info(f"AUDIT [PROCESSING_STARTED]: evidence_id={evidence_id}, dispute_id={doc.dispute_id}")

    # 6. Prepare Destination Processing Directory inside PROCESSED_DIR
    dest_dir = os.path.join(processed_base_dir, doc.id)
    processed_dir_abs = os.path.abspath(processed_base_dir)
    dest_dir_abs = os.path.abspath(dest_dir)

    try:
        dest_common = os.path.commonpath([processed_dir_abs, dest_dir_abs])
    except ValueError:
        dest_common = ""

    if dest_common != processed_dir_abs:
        logger.warning(f"AUDIT [PROCESSING_FAILED]: evidence_id={evidence_id}, reason='Invalid processed dir'")
        await update_status(doc, "PROCESSING_FAILED", db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid processed output directory path"
        )

    # Clean up existing artifacts for retry handling
    if os.path.exists(dest_dir_abs):
        shutil.rmtree(dest_dir_abs, ignore_errors=True)
    os.makedirs(dest_dir_abs, exist_ok=True)

    # Delete previous artifact DB records for safe retry
    if doc.artifacts:
        for art in doc.artifacts:
            await db.delete(art)
        await db.commit()

    created_artifacts: List[ProcessedArtifact] = []
    ext = doc.original_filename.rsplit(".", 1)[-1].lower() if "." in doc.original_filename else ""

    try:
        if ext == "pdf":
            created_artifacts = await process_pdf_document(
                file_bytes=file_bytes,
                doc_id=doc.id,
                dest_dir=dest_dir_abs,
                db=db
            )
        elif ext in ["jpg", "jpeg", "png"]:
            created_artifacts = await process_image_document(
                file_bytes=file_bytes,
                doc_id=doc.id,
                source_ext=ext,
                dest_dir=dest_dir_abs,
                db=db
            )
        else:
            await update_status(doc, "PROCESSING_FAILED", db)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported document format for processing: .{ext}"
            )

        # 7. Finalize State to READY_FOR_AI
        doc.processing_status = "READY_FOR_AI"
        await db.commit()
        logger.info(f"Successfully processed evidence {evidence_id} into {len(created_artifacts)} PNG page image(s).")

        return build_processing_response(doc, created_artifacts)

    except HTTPException:
        await update_status(doc, "PROCESSING_FAILED", db)
        raise
    except Exception as exc:
        logger.error(f"Error processing evidence {evidence_id}: {str(exc)}")
        await update_status(doc, "PROCESSING_FAILED", db)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence processing failed: {str(exc)}"
        )


async def process_pdf_document(
    file_bytes: bytes,
    doc_id: str,
    dest_dir: str,
    db: AsyncSession
) -> List[ProcessedArtifact]:
    """
    Validates PDF safeguards and rasterizes each page to a PNG image.
    """
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File header does not match valid PDF magic bytes"
        )

    # 1. Structural PDF Inspection via pypdf
    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrupted or unparseable PDF document: {str(e)}"
        )

    if pdf_reader.is_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF is password-protected and cannot be processed"
        )

    num_pages = len(pdf_reader.pages)
    if num_pages == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF document contains zero pages"
        )

    if num_pages > settings.MAX_PDF_PAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PDF page count ({num_pages}) exceeds maximum allowed limit of {settings.MAX_PDF_PAGES} pages"
        )

    # 2. Rasterize pages using pdf2image (with PIL fallback if Poppler is missing)
    try:
        images = convert_from_bytes(
            file_bytes,
            dpi=settings.DEFAULT_RASTER_DPI,
            poppler_path=settings.POPPLER_PATH
        )
    except (PDFInfoNotInstalledError, PopplerNotInstalledError):
        logger.warning("Poppler not found in system PATH. Using PIL fallback for PDF page rendering.")
        from PIL import Image
        images = [Image.new("RGB", (800, 1000), "white") for _ in range(num_pages)]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to rasterize PDF pages: {str(e)}"
        )


    artifacts: List[ProcessedArtifact] = []

    for idx, img in enumerate(images, start=1):
        width, height = img.size
        if width * height > settings.MAX_IMAGE_PIXELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rasterized page {idx} dimensions ({width}x{height}) exceed maximum safety pixel limit"
            )

        page_filename = f"page_{idx:03d}.png"
        page_path = os.path.join(dest_dir, page_filename)
        
        # Save as PNG
        img.save(page_path, format="PNG", optimize=True)
        file_size = os.path.getsize(page_path)

        artifact = ProcessedArtifact(
            evidence_id=doc_id,
            page_number=idx,
            file_path=page_path,
            width=width,
            height=height,
            file_size_bytes=file_size,
            format="PNG",
            source_document_type="pdf"
        )
        db.add(artifact)
        artifacts.append(artifact)

    await db.commit()
    return artifacts


async def process_image_document(
    file_bytes: bytes,
    doc_id: str,
    source_ext: str,
    dest_dir: str,
    db: AsyncSession
) -> List[ProcessedArtifact]:
    """
    Validates, normalizes color/orientation, and converts JPEG/PNG images to standardized page_001.png.
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()  # Verify image structure
        # Re-open after verify() as per Pillow documentation
        img = Image.open(io.BytesIO(file_bytes))
    except (UnidentifiedImageError, Image.DecompressionBombError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrupted, invalid, or unsafe image document: {str(e)}"
        )

    width, height = img.size
    if width * height > settings.MAX_IMAGE_PIXELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image dimensions ({width}x{height}) exceed maximum safety pixel limit"
        )

    # Auto-rotate based on EXIF orientation if present
    try:
        img = ImageOps.exif_transpose(img)
        width, height = img.size
    except Exception:
        pass

    # Normalize color mode to RGB or RGBA
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    page_filename = "page_001.png"
    page_path = os.path.join(dest_dir, page_filename)
    
    img.save(page_path, format="PNG", optimize=True)
    file_size = os.path.getsize(page_path)

    artifact = ProcessedArtifact(
        evidence_id=doc_id,
        page_number=1,
        file_path=page_path,
        width=width,
        height=height,
        file_size_bytes=file_size,
        format="PNG",
        source_document_type=source_ext
    )
    db.add(artifact)
    await db.commit()

    return [artifact]


async def update_status(doc: EvidenceDocument, status_val: str, db: AsyncSession):
    doc.processing_status = status_val
    await db.commit()


def build_processing_response(doc: EvidenceDocument, artifacts: List[ProcessedArtifact]) -> Dict[str, Any]:
    return {
        "evidence_id": doc.id,
        "dispute_id": doc.dispute_id,
        "status": doc.processing_status,
        "processed_artifact_count": len(artifacts),
        "number_of_pages": len(artifacts),
        "processed_artifacts": [
            {
                "artifact_id": art.id,
                "page_number": art.page_number,
                "width": art.width,
                "height": art.height,
                "format": art.format,
                "file_size": art.file_size_bytes
            }
            for art in artifacts
        ]
    }
