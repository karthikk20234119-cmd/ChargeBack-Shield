"""
Typed Schemas for Razorpay Evidence Reference Extraction — Task 3.3A

Represents extracted evidence document references, invalid items,
and extraction summary results.
"""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    """
    Typed internal schema for a single extracted document reference.

    Deduplicated by razorpay_doc_id while preserving all associated
    evidence categories.
    """

    razorpay_doc_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Validated Razorpay document ID e.g. doc_AHfqOvkldwsbqt",
    )
    razorpay_evidence_type: str = Field(
        ...,
        description="Primary evidence category e.g. shipping_proof, billing_proof",
    )
    categories: List[str] = Field(
        default_factory=list,
        description="All evidence categories associated with this document ID",
    )
    evidence_subtype: Optional[str] = Field(
        default=None,
        description="Optional evidence subtype (e.g. 'type' from 'others' object)",
    )
    source_dispute_id: Optional[str] = Field(
        default=None,
        description="Razorpay dispute ID that owns this evidence reference",
    )


class EvidenceReferenceInvalidItem(BaseModel):
    """
    Details of a malformed or invalid item encountered during extraction.
    """

    category: Optional[str] = Field(
        default=None, description="Category under which invalid item was found"
    )
    raw_value: Any = Field(
        default=None, description="Raw invalid value encountered"
    )
    reason: str = Field(..., description="Explanation of why item was rejected")


class EvidenceReferenceExtractionResult(BaseModel):
    """
    Result of an evidence reference extraction operation.
    """

    references: List[EvidenceReference] = Field(
        default_factory=list,
        description="List of valid, deduplicated document references",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of non-fatal warnings generated during extraction",
    )
    invalid_items: List[EvidenceReferenceInvalidItem] = Field(
        default_factory=list,
        description="Structured details of any invalid items rejected",
    )
