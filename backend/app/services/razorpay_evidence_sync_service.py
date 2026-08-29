"""
Razorpay Evidence Synchronization Orchestration Service — Phase 3 Task 3.3E

Connects read-only RazorpayClient, EvidenceReferenceExtractor (Task 3.3A),
RazorpayService document metadata validator (Task 3.3B), binary content stream (Task 3.3C),
and RazorpayEvidenceIngestionService (Task 3.3D) to securely synchronize all evidence
documents for a dispute.

SAFETY & BOUNDARY GUARANTEES:
- ZERO AI calls
- ZERO PDF rasterization / image processing
- ZERO ExtractedEvidence or ProcessedArtifact creation
- ZERO dispute financial field modifications (payment_id, amount, currency)
- ZERO policy evaluation
- ZERO Razorpay mutation API calls (read-only operations only)
- Per-document fault isolation (partial success supported)
- Idempotent re-runs (returns UNCHANGED / DUPLICATE with 0 duplicate files/rows)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.config import settings
from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.schemas.evidence_sync import (
    DisputeEvidenceSyncResult,
    EvidenceSyncItemResult,
)
from backend.app.services.evidence_reference_extractor import extract_evidence_references
from backend.app.services.razorpay_client import RazorpayClient
from backend.app.services.razorpay_errors import (
    RazorpayAuthenticationError,
    RazorpayClientError,
    RazorpayNotFoundError,
)
from backend.app.services.razorpay_evidence_ingestion_service import (
    RazorpayEvidenceIngestionService,
)
from backend.app.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)


class RazorpayEvidenceSyncService:
    """Orchestration service for synchronizing Razorpay dispute evidence documents."""

    def __init__(
        self,
        razorpay_service: RazorpayService,
        ingestion_service: Optional[RazorpayEvidenceIngestionService] = None,
        upload_dir: Optional[str] = None,
    ):
        self._razorpay_service = razorpay_service
        self._ingestion_service = (
            ingestion_service or RazorpayEvidenceIngestionService(upload_dir=upload_dir)
        )

    async def sync_dispute_evidence(
        self,
        dispute_id: str,
        db: AsyncSession,
        override_upload_dir: Optional[str] = None,
    ) -> DisputeEvidenceSyncResult:
        """
        Synchronize all evidence documents for a dispute from Razorpay to local storage.

        Flow:
        1. Verify local dispute exists
        2. Fetch Razorpay dispute via read-only client
        3. Extract evidence references
        4. Sequentially ingest each evidence reference independently (fault isolation)
        5. Return aggregate DisputeEvidenceSyncResult
        """
        timestamp_str = datetime.utcnow().isoformat()

        # -------------------------------------------------------------------
        # 1. Local Dispute Existence Check
        # -------------------------------------------------------------------
        stmt = select(Dispute).where(Dispute.id == dispute_id)
        res = await db.execute(stmt)
        dispute = res.scalar_one_or_none()

        if not dispute:
            reason = f"Local dispute '{dispute_id}' not found"
            logger.warning(
                f"AUDIT [SYNC_FAILED]: dispute_id={dispute_id}, reason='{reason}', timestamp={timestamp_str}"
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=reason)

        # -------------------------------------------------------------------
        # 2. Fetch Razorpay Dispute via Read-Only Client
        # -------------------------------------------------------------------
        try:
            rzp_dispute = await self._razorpay_service.get_dispute(dispute_id)
        except RazorpayAuthenticationError as auth_err:
            logger.error(
                f"AUDIT [SYNC_FAILED]: dispute_id={dispute_id}, reason='Authentication failure', timestamp={timestamp_str}"
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Razorpay API authentication failed",
            ) from auth_err
        except RazorpayNotFoundError as nf_err:
            logger.warning(
                f"AUDIT [SYNC_FAILED]: dispute_id={dispute_id}, reason='Dispute not found on Razorpay', timestamp={timestamp_str}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dispute '{dispute_id}' not found on Razorpay",
            ) from nf_err
        except RazorpayClientError as client_err:
            logger.error(
                f"AUDIT [SYNC_FAILED]: dispute_id={dispute_id}, reason='{client_err.message}', timestamp={timestamp_str}"
            )
            raise HTTPException(
                status_code=client_err.status_code or status.HTTP_502_BAD_GATEWAY,
                detail=client_err.message,
            ) from client_err

        # -------------------------------------------------------------------
        # 3. Extract Evidence References (Task 3.3A)
        # -------------------------------------------------------------------
        extraction_result = extract_evidence_references(rzp_dispute.model_dump())
        discovered = extraction_result.references

        if not discovered:
            logger.info(
                f"AUDIT [SYNC_COMPLETED]: dispute_id={dispute_id}, status=NO_EVIDENCE, discovered=0, timestamp={timestamp_str}"
            )
            return DisputeEvidenceSyncResult(
                dispute_id=dispute_id,
                status="NO_EVIDENCE",
                discovered_count=0,
                successful_count=0,
                duplicate_count=0,
                failed_count=0,
                results=[],
            )

        logger.info(
            f"AUDIT [SYNC_STARTED]: dispute_id={dispute_id}, discovered={len(discovered)}, timestamp={timestamp_str}"
        )

        # -------------------------------------------------------------------
        # 4. Sequential Per-Document Ingestion (Fault Isolation)
        # -------------------------------------------------------------------
        item_results: List[EvidenceSyncItemResult] = []
        successful_count = 0
        duplicate_count = 0
        failed_count = 0

        for ref in discovered:
            doc_id = ref.razorpay_doc_id
            category = ref.razorpay_evidence_type

            logger.info(
                f"AUDIT [DOCUMENT_DISCOVERED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, category={category}, timestamp={timestamp_str}"
            )

            try:
                # 4a. Source Dispute ID Identity Check
                if ref.source_dispute_id and ref.source_dispute_id != dispute_id:
                    reason = f"Source dispute ID mismatch '{ref.source_dispute_id}' != '{dispute_id}'"
                    logger.warning(
                        f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, reason='{reason}', timestamp={timestamp_str}"
                    )
                    item_results.append(
                        EvidenceSyncItemResult(
                            razorpay_doc_id=doc_id,
                            evidence_type=category,
                            status="FAILED",
                            failure_category="IDENTITY_MISMATCH",
                            failure_reason=reason,
                        )
                    )
                    failed_count += 1
                    continue

                # 4b. Tier 1 Duplicate Check (dispute_id, razorpay_doc_id)
                t1_stmt = select(EvidenceDocument).where(
                    EvidenceDocument.dispute_id == dispute_id,
                    EvidenceDocument.razorpay_doc_id == doc_id,
                )
                t1_doc = (await db.execute(t1_stmt)).scalar_one_or_none()
                if t1_doc:
                    logger.info(
                        f"AUDIT [DOCUMENT_DUPLICATE]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, tier=1, timestamp={timestamp_str}"
                    )
                    item_results.append(
                        EvidenceSyncItemResult(
                            razorpay_doc_id=doc_id,
                            evidence_type=category,
                            status="DUPLICATE",
                            local_evidence_id=t1_doc.id,
                            file_hash=t1_doc.file_hash,
                            file_size_bytes=t1_doc.file_size_bytes,
                        )
                    )
                    duplicate_count += 1
                    continue

                # 4c. Fetch Document Metadata & Validate Pre-Flight (Task 3.3B)
                try:
                    metadata = await self._razorpay_service.get_document_metadata(doc_id)
                    logger.info(
                        f"AUDIT [DOCUMENT_METADATA_VALIDATED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, mime={metadata.mime_type}, size={metadata.size}, timestamp={timestamp_str}"
                    )
                except HTTPException as meta_http_err:
                    cat = "METADATA_INVALID"
                    detail_str = str(meta_http_err.detail)
                    if meta_http_err.status_code == 404:
                        cat = "DOCUMENT_NOT_FOUND"
                    elif "MIME" in detail_str or "unsupported" in detail_str.lower():
                        cat = "UNSUPPORTED_MIME"
                    elif "size" in detail_str.lower() or "ceiling" in detail_str.lower():
                        cat = "OVERSIZED"

                    logger.warning(
                        f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, reason='{detail_str}', timestamp={timestamp_str}"
                    )
                    item_results.append(
                        EvidenceSyncItemResult(
                            razorpay_doc_id=doc_id,
                            evidence_type=category,
                            status="FAILED",
                            failure_category=cat,
                            failure_reason=detail_str,
                        )
                    )
                    failed_count += 1
                    continue
                except RazorpayNotFoundError:
                    reason = "Document metadata not found on Razorpay"
                    logger.warning(
                        f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, reason='{reason}', timestamp={timestamp_str}"
                    )
                    item_results.append(
                        EvidenceSyncItemResult(
                            razorpay_doc_id=doc_id,
                            evidence_type=category,
                            status="FAILED",
                            failure_category="DOCUMENT_NOT_FOUND",
                            failure_reason=reason,
                        )
                    )
                    failed_count += 1
                    continue
                except Exception as meta_err:
                    reason = str(meta_err)
                    logger.warning(
                        f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, reason='{reason}', timestamp={timestamp_str}"
                    )
                    item_results.append(
                        EvidenceSyncItemResult(
                            razorpay_doc_id=doc_id,
                            evidence_type=category,
                            status="FAILED",
                            failure_category="METADATA_INVALID",
                            failure_reason=reason,
                        )
                    )
                    failed_count += 1
                    continue

                # 4d. Stream Binary Content (Task 3.3C)
                max_limit = (
                    settings.MAX_PDF_SIZE_BYTES
                    if metadata.mime_type == "application/pdf"
                    else settings.MAX_IMAGE_SIZE_BYTES
                )
                try:
                    stream = await self._razorpay_service.stream_document_content(
                        doc_id, max_allowed_bytes=max_limit
                    )
                except Exception as stream_err:
                    reason = f"Stream error: {stream_err}"
                    logger.warning(
                        f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, reason='{reason}', timestamp={timestamp_str}"
                    )
                    item_results.append(
                        EvidenceSyncItemResult(
                            razorpay_doc_id=doc_id,
                            evidence_type=category,
                            status="FAILED",
                            failure_category="STREAM_FAILED",
                            failure_reason=reason,
                        )
                    )
                    failed_count += 1
                    continue

                # 4e. Secure Local Ingestion (Task 3.3D)
                try:
                    ingest_res = await self._ingestion_service.ingest_evidence(
                        dispute_id=dispute_id,
                        evidence_ref=ref,
                        metadata=metadata,
                        stream=stream,
                        db=db,
                        override_upload_dir=override_upload_dir,
                    )

                    if ingest_res.status == "SUCCESS":
                        logger.info(
                            f"AUDIT [DOCUMENT_SYNCED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, local_doc_id={ingest_res.document_id}, timestamp={timestamp_str}"
                        )
                        item_results.append(
                            EvidenceSyncItemResult(
                                razorpay_doc_id=doc_id,
                                evidence_type=category,
                                status="SUCCESS",
                                local_evidence_id=ingest_res.document_id,
                                file_hash=ingest_res.file_hash,
                                file_size_bytes=ingest_res.file_size_bytes,
                            )
                        )
                        successful_count += 1
                    elif ingest_res.status == "DUPLICATE":
                        logger.info(
                            f"AUDIT [DOCUMENT_DUPLICATE]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, tier=2, timestamp={timestamp_str}"
                        )
                        item_results.append(
                            EvidenceSyncItemResult(
                                razorpay_doc_id=doc_id,
                                evidence_type=category,
                                status="DUPLICATE",
                                local_evidence_id=ingest_res.document_id,
                                file_hash=ingest_res.file_hash,
                                file_size_bytes=ingest_res.file_size_bytes,
                                failure_reason=ingest_res.reason,
                            )
                        )
                        duplicate_count += 1
                    else:
                        item_results.append(
                            EvidenceSyncItemResult(
                                razorpay_doc_id=doc_id,
                                evidence_type=category,
                                status="FAILED",
                                failure_category="STORAGE_FAILED",
                                failure_reason=ingest_res.reason or "Ingestion rejected",
                            )
                        )
                        failed_count += 1

                except HTTPException as ingest_http_err:
                    cat = "UNKNOWN_ERROR"
                    detail_str = str(ingest_http_err.detail)
                    if "magic bytes" in detail_str.lower():
                        cat = "MAGIC_BYTES_INVALID"
                    elif "ceiling" in detail_str.lower() or "exceeds" in detail_str.lower():
                        cat = "OVERSIZED"
                    elif "hash" in detail_str.lower():
                        cat = "HASH_MISMATCH"
                    elif "mime" in detail_str.lower() or "contradictory" in detail_str.lower():
                        cat = "UNSUPPORTED_MIME"
                    elif "identity" in detail_str.lower():
                        cat = "IDENTITY_MISMATCH"
                    elif "database" in detail_str.lower():
                        cat = "DATABASE_FAILED"

                    logger.warning(
                        f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, reason='{detail_str}', timestamp={timestamp_str}"
                    )
                    item_results.append(
                        EvidenceSyncItemResult(
                            razorpay_doc_id=doc_id,
                            evidence_type=category,
                            status="FAILED",
                            failure_category=cat,
                            failure_reason=detail_str,
                        )
                    )
                    failed_count += 1

                except Exception as ingest_err:
                    logger.error(
                        f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, reason='Unexpected error: {ingest_err}', timestamp={timestamp_str}"
                    )
                    item_results.append(
                        EvidenceSyncItemResult(
                            razorpay_doc_id=doc_id,
                            evidence_type=category,
                            status="FAILED",
                            failure_category="UNKNOWN_ERROR",
                            failure_reason=str(ingest_err),
                        )
                    )
                    failed_count += 1

            except Exception as unhandled_doc_err:
                logger.error(
                    f"AUDIT [DOCUMENT_REJECTED]: dispute_id={dispute_id}, razorpay_doc_id={doc_id}, reason='Unhandled doc error: {unhandled_doc_err}', timestamp={timestamp_str}"
                )
                item_results.append(
                    EvidenceSyncItemResult(
                        razorpay_doc_id=doc_id,
                        evidence_type=category,
                        status="FAILED",
                        failure_category="UNKNOWN_ERROR",
                        failure_reason=str(unhandled_doc_err),
                    )
                )
                failed_count += 1

        # -------------------------------------------------------------------
        # 5. Compute Aggregate Status & Audit Completion
        # -------------------------------------------------------------------
        discovered_count = len(discovered)
        if discovered_count == 0:
            overall_status = "NO_EVIDENCE"
        elif duplicate_count == discovered_count:
            overall_status = "UNCHANGED"
        elif successful_count > 0 and failed_count == 0:
            overall_status = "SUCCESS"
        elif successful_count > 0 and failed_count > 0:
            overall_status = "PARTIAL_SUCCESS"
        elif successful_count == 0 and failed_count > 0:
            overall_status = "FAILED"
        else:
            overall_status = (
                "SUCCESS" if (successful_count + duplicate_count) > 0 else "FAILED"
            )

        logger.info(
            f"AUDIT [SYNC_COMPLETED]: dispute_id={dispute_id}, status={overall_status}, "
            f"discovered={discovered_count}, successful={successful_count}, "
            f"duplicates={duplicate_count}, failed={failed_count}, timestamp={timestamp_str}"
        )

        return DisputeEvidenceSyncResult(
            dispute_id=dispute_id,
            status=overall_status,
            discovered_count=discovered_count,
            successful_count=successful_count,
            duplicate_count=duplicate_count,
            failed_count=failed_count,
            results=item_results,
        )
