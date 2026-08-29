"""
Razorpay Evidence Local Ingestion Service — Phase 3 Task 3.3D

Consumes bounded binary streams (DocumentContentStream from Task 3.3C),
performs magic-byte validation, MIME consistency checking, size ceiling enforcement,
SHA-256 verification, path safety checks, Tier 1 & Tier 2 duplicate detection,
and atomic file/DB persistence, producing a validated local EvidenceDocument.

SAFETY & BOUNDARY GUARANTEES:
- ZERO AI calls
- ZERO PDF rasterization / image processing
- ZERO ExtractedEvidence or ProcessedArtifact creation
- ZERO policy evaluation
- ZERO Razorpay mutation API calls
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.config import settings
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.schemas.razorpay import DocumentContentResult, RazorpayDocumentMetadataResponse
from backend.app.services.evidence_reference_extractor import EvidenceReference, validate_document_id
from backend.app.services.razorpay_client import DocumentContentStream
from backend.app.services.razorpay_errors import RazorpayValidationError
from backend.app.utils.file_processor import (
    ALLOWED_EXTENSIONS,
    MAGIC_HEADERS,
    MIME_TYPE_MAP,
    calculate_sha256,
    generate_internal_filename,
    sanitize_filename,
    validate_magic_bytes,
)

logger = logging.getLogger(__name__)


class IngestionResult(BaseModel):
    """Result summary of a secure local evidence ingestion operation."""

    status: str = Field(..., description="SUCCESS, DUPLICATE, or REJECTED")
    document_id: Optional[str] = Field(default=None, description="Local EvidenceDocument ID")
    dispute_id: str = Field(..., description="Target dispute ID")
    razorpay_doc_id: str = Field(..., description="Razorpay document ID")
    file_hash: Optional[str] = Field(default=None, description="SHA-256 hash")
    file_size_bytes: Optional[int] = Field(default=None, description="Byte count")
    reason: Optional[str] = Field(default=None, description="Rejection or duplicate reason")
    model_config = {"arbitrary_types_allowed": True}


class RazorpayEvidenceIngestionService:
    """Service for ingesting Razorpay evidence binary streams securely into local storage."""

    def __init__(self, upload_dir: Optional[str] = None):
        self._upload_dir = upload_dir or settings.UPLOAD_DIR

    async def ingest_evidence(
        self,
        dispute_id: str,
        evidence_ref: EvidenceReference,
        metadata: RazorpayDocumentMetadataResponse,
        stream: DocumentContentStream,
        db: AsyncSession,
        override_upload_dir: Optional[str] = None,
        expected_sha256: Optional[str] = None,
    ) -> IngestionResult:
        """
        Securely ingests a Razorpay document stream into local storage and database.

        Steps:
        1. Validate dispute existence and identity alignment
        2. Tier 1 duplicate check (dispute_id, razorpay_doc_id)
        3. Stream chunks to temp file with magic-byte and MIME consistency check
        4. Size ceiling enforcement during streaming
        5. SHA-256 calculation & Tier 2 duplicate check (dispute_id, file_hash)
        6. Path boundary verification & atomic rename
        7. Database transaction persistence with rollback & disk cleanup guarantees
        """
        timestamp_str = datetime.utcnow().isoformat()
        upload_dir = override_upload_dir or self._upload_dir
        os.makedirs(upload_dir, exist_ok=True)
        tmp_dir = os.path.join(upload_dir, ".tmp")
        os.makedirs(tmp_dir, exist_ok=True)

        logger.info(
            f"AUDIT [DOCUMENT_DISCOVERED]: dispute_id={dispute_id}, "
            f"razorpay_doc_id={metadata.id}, category={evidence_ref.razorpay_evidence_type}, "
            f"timestamp={timestamp_str}"
        )

        # -------------------------------------------------------------------
        # 1. Identity & Ownership Pre-Checks
        # -------------------------------------------------------------------
        stmt = select(Dispute).where(Dispute.id == dispute_id)
        res = await db.execute(stmt)
        dispute = res.scalar_one_or_none()

        if not dispute:
            reason = f"Target dispute {dispute_id} not found"
            logger.warning(
                f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, "
                f"razorpay_doc_id={metadata.id}, reason='{reason}', timestamp={timestamp_str}"
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=reason)

        if evidence_ref.source_dispute_id != dispute_id:
            reason = (
                f"Identity mismatch: evidence reference source_dispute_id "
                f"'{evidence_ref.source_dispute_id}' != target dispute_id '{dispute_id}'"
            )
            logger.warning(
                f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, "
                f"razorpay_doc_id={metadata.id}, reason='{reason}', timestamp={timestamp_str}"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

        if not (evidence_ref.razorpay_doc_id == metadata.id == stream.razorpay_doc_id):
            reason = (
                f"Identity mismatch: reference doc_id '{evidence_ref.razorpay_doc_id}', "
                f"metadata doc_id '{metadata.id}', stream doc_id '{stream.razorpay_doc_id}'"
            )
            logger.warning(
                f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, "
                f"razorpay_doc_id={metadata.id}, reason='{reason}', timestamp={timestamp_str}"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

        # -------------------------------------------------------------------
        # 2. Tier 1 Duplicate Detection (dispute_id, razorpay_doc_id)
        # -------------------------------------------------------------------
        t1_stmt = select(EvidenceDocument).where(
            EvidenceDocument.dispute_id == dispute_id,
            EvidenceDocument.razorpay_doc_id == metadata.id,
        )
        t1_res = await db.execute(t1_stmt)
        existing_t1 = t1_res.scalar_one_or_none()

        if existing_t1:
            logger.info(
                f"AUDIT [DOCUMENT_DUPLICATE]: dispute_id={dispute_id}, "
                f"razorpay_doc_id={metadata.id}, tier=1, existing_doc_id={existing_t1.id}, "
                f"timestamp={timestamp_str}"
            )
            return IngestionResult(
                status="DUPLICATE",
                document_id=existing_t1.id,
                dispute_id=dispute_id,
                razorpay_doc_id=metadata.id,
                file_hash=existing_t1.file_hash,
                file_size_bytes=existing_t1.file_size_bytes,
                reason="Tier 1 duplicate (razorpay_doc_id already ingested for dispute)",
            )

        # -------------------------------------------------------------------
        # 3. Incremental Stream-to-Disk with Magic Byte & MIME Validation
        # -------------------------------------------------------------------
        temp_fd, temp_path = tempfile.mkstemp(dir=tmp_dir, suffix=".tmp")
        hasher = hashlib.sha256()
        total_bytes = 0
        magic_ext: Optional[str] = None
        first_chunk_checked = False

        try:
            with os.fdopen(temp_fd, "wb") as f_out:
                try:
                    async for chunk in stream.chunks():
                        if not chunk:
                            continue

                        total_bytes += len(chunk)
                        hasher.update(chunk)
                        f_out.write(chunk)

                        # Initial magic-byte inspection on leading bytes
                        if not first_chunk_checked:
                            f_out.flush()
                            with open(temp_path, "rb") as f_in:
                                leading_bytes = f_in.read(32)

                            magic_ext = self._detect_magic_extension(leading_bytes)
                            if not magic_ext:
                                reason = "File content magic bytes do not match any supported format (PDF, JPEG, PNG)"
                                logger.warning(
                                    f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, "
                                    f"razorpay_doc_id={metadata.id}, reason='{reason}', timestamp={timestamp_str}"
                                )
                                raise HTTPException(
                                    status_code=status.HTTP_400_BAD_REQUEST, detail=reason
                                )

                            # Enforce MIME consistency against magic bytes
                            self._validate_mime_consistency(
                                magic_ext=magic_ext,
                                metadata_mime=metadata.mime_type,
                                stream_content_type=stream.content_type,
                                dispute_id=dispute_id,
                                doc_id=metadata.id,
                            )
                            first_chunk_checked = True

                        # Size ceiling enforcement during streaming
                        max_limit = (
                            settings.MAX_PDF_SIZE_BYTES
                            if magic_ext == "pdf"
                            else settings.MAX_IMAGE_SIZE_BYTES
                        )
                        if total_bytes > max_limit:
                            reason = f"Streamed byte count ({total_bytes}) exceeds ceiling of {max_limit} bytes"
                            logger.warning(
                                f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, "
                                f"razorpay_doc_id={metadata.id}, reason='{reason}', timestamp={timestamp_str}"
                            )
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST, detail=reason
                            )
                except RazorpayValidationError as val_err:
                    logger.warning(
                        f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, "
                        f"razorpay_doc_id={metadata.id}, reason='{val_err.message}', timestamp={timestamp_str}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail=val_err.message
                    ) from val_err

            if total_bytes == 0 or not magic_ext:
                reason = "Downloaded file stream is empty (0 bytes)"
                logger.warning(
                    f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, "
                    f"razorpay_doc_id={metadata.id}, reason='{reason}', timestamp={timestamp_str}"
                )
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

            # ---------------------------------------------------------------
            # 4. SHA-256 Verification & Tier 2 Duplicate Check
            # ---------------------------------------------------------------
            calculated_hash = hasher.hexdigest()
            target_hash = expected_sha256 or (stream.sha256 if stream.sha256 else None)

            if target_hash and target_hash != calculated_hash:
                reason = (
                    f"SHA-256 hash mismatch: expected hash '{target_hash}' != "
                    f"file calculated hash '{calculated_hash}'"
                )
                logger.warning(
                    f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, "
                    f"razorpay_doc_id={metadata.id}, reason='{reason}', timestamp={timestamp_str}"
                )
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

            # Tier 2 Duplicate Check (dispute_id, file_hash)
            t2_stmt = select(EvidenceDocument).where(
                EvidenceDocument.dispute_id == dispute_id,
                EvidenceDocument.file_hash == calculated_hash,
            )
            t2_res = await db.execute(t2_stmt)
            existing_t2 = t2_res.scalar_one_or_none()

            if existing_t2:
                # Cleanup temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

                logger.info(
                    f"AUDIT [DOCUMENT_DUPLICATE]: dispute_id={dispute_id}, "
                    f"razorpay_doc_id={metadata.id}, tier=2, sha256={calculated_hash}, "
                    f"existing_doc_id={existing_t2.id}, timestamp={timestamp_str}"
                )
                return IngestionResult(
                    status="DUPLICATE",
                    document_id=existing_t2.id,
                    dispute_id=dispute_id,
                    razorpay_doc_id=metadata.id,
                    file_hash=calculated_hash,
                    file_size_bytes=total_bytes,
                    reason="Tier 2 duplicate (identical content SHA-256 hash already exists)",
                )

            # ---------------------------------------------------------------
            # 5. Path Safety Verification & Atomic File Move
            # ---------------------------------------------------------------
            internal_filename = generate_internal_filename(magic_ext)
            final_dest_path = os.path.join(upload_dir, internal_filename)

            # Enforce path boundary safety
            abs_upload_dir = os.path.abspath(upload_dir)
            abs_final_path = os.path.abspath(final_dest_path)
            if os.path.commonpath([abs_upload_dir, abs_final_path]) != abs_upload_dir:
                reason = "Path traversal attack detected during target path resolution"
                logger.error(
                    f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, "
                    f"razorpay_doc_id={metadata.id}, reason='{reason}', timestamp={timestamp_str}"
                )
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

            shutil.move(temp_path, final_dest_path)

            # ---------------------------------------------------------------
            # 6. Database Persistence & Rollback Cleanup Guarantees
            # ---------------------------------------------------------------
            orig_name = sanitize_filename(metadata.name) or f"{metadata.id}.{magic_ext}"
            derived_mime = MIME_TYPE_MAP.get(magic_ext, "application/octet-stream")

            doc = EvidenceDocument(
                id=str(uuid.uuid4()),
                dispute_id=dispute_id,
                razorpay_doc_id=metadata.id,
                original_filename=orig_name,
                internal_filename=internal_filename,
                file_path=final_dest_path,
                file_hash=calculated_hash,
                file_size_bytes=total_bytes,
                mime_type=derived_mime,
                document_type=evidence_ref.razorpay_evidence_type,  # Preserve Razorpay category
                processing_status="UPLOADED",
            )

            try:
                db.add(doc)
                await db.commit()
                await db.refresh(doc)
            except Exception as db_exc:
                await db.rollback()
                if os.path.exists(final_dest_path):
                    os.remove(final_dest_path)
                logger.error(
                    f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, "
                    f"razorpay_doc_id={metadata.id}, reason='Database commit error: {db_exc}', "
                    f"timestamp={timestamp_str}"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database persistence failure: {db_exc}",
                ) from db_exc

            logger.info(
                f"AUDIT [DOCUMENT_DOWNLOADED]: dispute_id={dispute_id}, "
                f"razorpay_doc_id={metadata.id}, local_doc_id={doc.id}, "
                f"sha256={calculated_hash}, size={total_bytes}, "
                f"category={evidence_ref.razorpay_evidence_type}, timestamp={timestamp_str}"
            )

            return IngestionResult(
                status="SUCCESS",
                document_id=doc.id,
                dispute_id=dispute_id,
                razorpay_doc_id=metadata.id,
                file_hash=calculated_hash,
                file_size_bytes=total_bytes,
            )

        except Exception:
            # Cleanup temp file on any failure prior to move
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

    @staticmethod
    def _detect_magic_extension(file_bytes: bytes) -> Optional[str]:
        """Detect file extension from leading binary magic bytes."""
        if not file_bytes:
            return None
        for ext, headers in MAGIC_HEADERS.items():
            for header in headers:
                if file_bytes.startswith(header):
                    return "jpg" if ext == "jpeg" else ext
        return None

    @staticmethod
    def _validate_mime_consistency(
        magic_ext: str,
        metadata_mime: str,
        stream_content_type: str,
        dispute_id: str,
        doc_id: str,
    ) -> None:
        """
        Validate consistency among binary magic bytes, external metadata MIME, and HTTP transport Content-Type.

        Magic bytes are authoritative. Contradictions (e.g. magic=PDF, metadata=image/png) raise HTTP 400.
        """
        meta_mime_norm = (metadata_mime or "").lower().strip()
        stream_mime_norm = (stream_content_type or "").lower().strip()

        # Categorize magic extension into 'pdf' or 'image'
        magic_category = "pdf" if magic_ext == "pdf" else "image"

        # Check metadata MIME category
        if "pdf" in meta_mime_norm and magic_category != "pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Contradictory document format: external metadata claims PDF "
                    f"('{metadata_mime}'), but binary content magic bytes indicate '{magic_ext}' image."
                ),
            )

        if ("image" in meta_mime_norm or "jpeg" in meta_mime_norm or "png" in meta_mime_norm) and magic_category != "image":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Contradictory document format: external metadata claims image "
                    f"('{metadata_mime}'), but binary content magic bytes indicate PDF."
                ),
            )

        # Check stream transport Content-Type category if provided (and not generic octet-stream)
        if stream_mime_norm and "octet-stream" not in stream_mime_norm:
            if "pdf" in stream_mime_norm and magic_category != "pdf":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Contradictory transport format: Content-Type header claims PDF "
                        f"('{stream_content_type}'), but binary content magic bytes indicate '{magic_ext}' image."
                    ),
                )
            if ("image" in stream_mime_norm or "jpeg" in stream_mime_norm or "png" in stream_mime_norm) and magic_category != "image":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Contradictory transport format: Content-Type header claims image "
                        f"('{stream_content_type}'), but binary content magic bytes indicate PDF."
                    ),
                )


# Helper function for service convenience
async def ingest_razorpay_evidence(
    dispute_id: str,
    evidence_ref: EvidenceReference,
    metadata: RazorpayDocumentMetadataResponse,
    stream: DocumentContentStream,
    db: AsyncSession,
    override_upload_dir: Optional[str] = None,
    expected_sha256: Optional[str] = None,
) -> IngestionResult:
    """Convenience helper to execute secure local evidence ingestion."""
    service = RazorpayEvidenceIngestionService(upload_dir=override_upload_dir)
    return await service.ingest_evidence(
        dispute_id=dispute_id,
        evidence_ref=evidence_ref,
        metadata=metadata,
        stream=stream,
        db=db,
        override_upload_dir=override_upload_dir,
        expected_sha256=expected_sha256,
    )
