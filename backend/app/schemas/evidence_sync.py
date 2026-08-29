"""
Typed Schemas for Razorpay Evidence Synchronization Orchestration — Task 3.3E

Defines per-document sync item results and aggregate dispute sync results.
"""

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class EvidenceSyncItemResult(BaseModel):
    """
    Typed summary of a single evidence document synchronization attempt.
    """

    razorpay_doc_id: str = Field(
        ..., min_length=1, max_length=64, description="Razorpay document ID"
    )
    evidence_type: str = Field(
        ..., description="Primary evidence category e.g. shipping_proof, billing_proof"
    )
    status: Literal["SUCCESS", "DUPLICATE", "FAILED"] = Field(
        ..., description="Per-document sync status"
    )
    local_evidence_id: Optional[str] = Field(
        default=None, description="Internal EvidenceDocument UUID if successful or duplicate"
    )
    file_hash: Optional[str] = Field(
        default=None, description="SHA-256 digest of file content"
    )
    file_size_bytes: Optional[int] = Field(
        default=None, description="Exact file size in bytes"
    )
    failure_category: Optional[str] = Field(
        default=None,
        description=(
            "Structured error category e.g. DOCUMENT_NOT_FOUND, METADATA_INVALID, "
            "UNSUPPORTED_MIME, OVERSIZED, STREAM_FAILED, HASH_MISMATCH, "
            "MAGIC_BYTES_INVALID, IDENTITY_MISMATCH, STORAGE_FAILED, DATABASE_FAILED, UNKNOWN_ERROR"
        ),
    )
    failure_reason: Optional[str] = Field(
        default=None, description="Detailed explanation of failure"
    )


class DisputeEvidenceSyncResult(BaseModel):
    """
    Aggregate result of a dispute evidence synchronization workflow.
    """

    dispute_id: str = Field(..., description="Target dispute ID")
    status: Literal["SUCCESS", "PARTIAL_SUCCESS", "NO_EVIDENCE", "UNCHANGED", "FAILED"] = Field(
        ..., description="Aggregate sync outcome status"
    )
    discovered_count: int = Field(
        default=0, ge=0, description="Total evidence references discovered"
    )
    successful_count: int = Field(
        default=0, ge=0, description="Count of newly ingested documents"
    )
    duplicate_count: int = Field(
        default=0, ge=0, description="Count of pre-existing duplicate documents"
    )
    failed_count: int = Field(
        default=0, ge=0, description="Count of failed document ingestions"
    )
    results: List[EvidenceSyncItemResult] = Field(
        default_factory=list, description="Per-document sync details"
    )
