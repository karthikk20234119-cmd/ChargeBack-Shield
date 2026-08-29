import os
import logging
from typing import Dict, Any
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.config import settings
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.utils.file_processor import (
    sanitize_filename,
    validate_extension_and_mime,
    validate_magic_bytes,
    calculate_sha256,
    generate_internal_filename
)

logger = logging.getLogger(__name__)

async def process_evidence_upload(
    dispute_id: str,
    file: UploadFile,
    db: AsyncSession,
    override_upload_dir: str = None
) -> Dict[str, Any]:
    """
    Validates and stores evidence files securely for a dispute.
    Enforces dispute existence, file size ceilings, magic byte validation, 
    SHA-256 duplicate detection, safe internal path generation, and DB persistence.
    """
    timestamp_str = logging.Formatter().formatTime(logging.LogRecord("", 0, "", 0, "", (), None))
    upload_dir = override_upload_dir or settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)

    # 1. Dispute Validation
    stmt = select(Dispute).where(Dispute.id == dispute_id)
    result = await db.execute(stmt)
    dispute = result.scalar_one_or_none()

    if not dispute:
        logger.warning(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='Dispute not found', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dispute with ID {dispute_id} not found"
        )

    # 2. File Presence & Filename Sanitization
    if not file or not file.filename:
        logger.warning(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='Missing file', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided in upload request"
        )

    original_filename = sanitize_filename(file.filename)
    
    # 3. Read File Bytes for Validation
    try:
        file_bytes = await file.read()
    except Exception as e:
        logger.error(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='File read error', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read uploaded file stream"
        )

    file_size = len(file_bytes)
    if file_size == 0:
        logger.warning(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='Empty file', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)"
        )

    # 4. Extension & MIME Validation
    try:
        ext, mime_type = validate_extension_and_mime(original_filename, file.content_type)
    except ValueError as val_err:
        logger.warning(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='{str(val_err)}', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )

    # 5. Content Security Magic Byte Validation
    if not validate_magic_bytes(file_bytes, ext):
        logger.warning(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='Magic byte validation failed for extension .{ext}', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content magic bytes do not match expected format for .{ext}"
        )

    # 6. File Size Limit Verification (Configurable)
    if ext == "pdf" and file_size > settings.MAX_PDF_SIZE_BYTES:
        logger.warning(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='PDF size {file_size} exceeds limit {settings.MAX_PDF_SIZE_BYTES}', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PDF file size ({file_size} bytes) exceeds maximum limit of {settings.MAX_PDF_SIZE_BYTES} bytes (2MB)"
        )

    if ext in ["jpg", "jpeg", "png"] and file_size > settings.MAX_IMAGE_SIZE_BYTES:
        logger.warning(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='Image size {file_size} exceeds limit {settings.MAX_IMAGE_SIZE_BYTES}', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image file size ({file_size} bytes) exceeds maximum limit of {settings.MAX_IMAGE_SIZE_BYTES} bytes (4MB)"
        )

    # 7. SHA-256 Hashing & Duplicate Detection
    sha256_hash = calculate_sha256(file_bytes)
    
    hash_stmt = select(EvidenceDocument).where(
        EvidenceDocument.dispute_id == dispute_id,
        EvidenceDocument.file_hash == sha256_hash
    )
    hash_res = await db.execute(hash_stmt)
    if hash_res.scalar_one_or_none():
        logger.warning(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='Duplicate SHA-256 content hash', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evidence document with this exact content (SHA-256) has already been uploaded for this dispute."
        )

    # 8. Safe Disk Storage
    internal_filename = generate_internal_filename(ext)
    target_path = os.path.join(upload_dir, internal_filename)
    
    # Extra safety check to guarantee target_path stays inside upload_dir
    abs_upload_dir = os.path.abspath(upload_dir)
    abs_target_path = os.path.abspath(target_path)
    if not abs_target_path.startswith(abs_upload_dir):
        logger.error(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='Path traversal detected', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid internal file destination"
        )

    try:
        with open(target_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        logger.error(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='Storage write failure: {str(e)}', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write evidence file to secure storage"
        )

    # 9. Database Record Persistence
    doc = EvidenceDocument(
        dispute_id=dispute_id,
        original_filename=original_filename,
        internal_filename=internal_filename,
        file_path=target_path,
        file_hash=sha256_hash,
        file_size_bytes=file_size,
        mime_type=mime_type,
        document_type="shipping_proof",
        processing_status="UPLOADED"
    )

    try:
        db.add(doc)
        await db.commit()
    except Exception as e:

        # Rollback disk file if DB commit fails
        if os.path.exists(target_path):
            os.remove(target_path)
        logger.error(f"AUDIT [Evidence upload rejected]: dispute_id={dispute_id}, reason='Database commit failure: {str(e)}', timestamp={timestamp_str}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record evidence document in database"
        )

    logger.info(f"AUDIT [Evidence upload accepted]: dispute_id={dispute_id}, evidence_id={doc.id}, sha256={sha256_hash}, timestamp={timestamp_str}")

    return {
        "evidence_id": doc.id,
        "dispute_id": doc.dispute_id,
        "filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "file_size": doc.file_size_bytes,
        "sha256": doc.file_hash,
        "status": doc.processing_status
    }
