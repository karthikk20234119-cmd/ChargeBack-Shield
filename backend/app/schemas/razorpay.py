from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field, field_validator

# --------------------------------------------------------------------------
# Existing schemas (from earlier planning — NOT exposed or implemented in
# Task 3.1, left untouched for future tasks)
# --------------------------------------------------------------------------

class RazorpayContestRequest(BaseModel):
    amount: int = Field(description="Disputed amount in paise")
    action: str = Field(description="Must be 'draft' or 'submit'")
    summary: str = Field(description="Explanation letter for representment")
    shipping_proof: Optional[List[str]] = Field(default=None, description="Array of doc_ids for shipping proof")
    billing_proof: Optional[List[str]] = Field(default=None, description="Array of doc_ids for billing proof")
    cancellation_proof: Optional[List[str]] = Field(default=None, description="Array of doc_ids for cancellation proof")
    explanation_letter: Optional[List[str]] = Field(default=None, description="Array of doc_ids for explanation letter")

# --------------------------------------------------------------------------
# Task 3.3B — Read-only Razorpay Document Metadata response schemas
# --------------------------------------------------------------------------

# Official Razorpay document purpose for dispute representment evidence
RAZORPAY_DISPUTE_DOCUMENT_PURPOSES = {"dispute_evidence"}

# Locally supported MIME types for evidence processing
SUPPORTED_EVIDENCE_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}


class RazorpayDocumentMetadataResponse(BaseModel):
    """
    Internal typed schema for Razorpay document metadata (GET /v1/documents/:id).

    Validated from external Razorpay API JSON responses.
    Does NOT download or store binary content.
    """

    id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Razorpay document ID e.g. doc_AHfqOvkldwsbqt",
    )
    entity: Literal["document"] = Field(
        ...,
        description="Must be 'document' — validates correct entity type",
    )
    purpose: str = Field(
        ...,
        description="Document purpose e.g. dispute_evidence",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Untrusted external document name",
    )
    size: int = Field(
        ...,
        ge=0,
        description="File size in bytes",
    )
    mime_type: str = Field(
        ...,
        min_length=1,
        description="MIME type e.g. application/pdf, image/jpeg, image/png",
    )
    created_at: int = Field(
        ...,
        description="Unix timestamp of document creation",
    )

    model_config = {"extra": "ignore"}


class DocumentContentResult(BaseModel):
    """
    Typed summary result of a completed document binary content stream.

    Documents exact downloaded byte length, raw Content-Type, and stream SHA-256 digest.
    """

    razorpay_doc_id: str = Field(
        ..., min_length=1, max_length=64, description="Razorpay document ID"
    )
    content_type: str = Field(
        ..., description="Raw transport Content-Type header value"
    )
    total_bytes: int = Field(..., ge=1, description="Exact downloaded byte count")
    sha256: str = Field(
        ..., min_length=64, max_length=64, description="SHA-256 hex digest of raw stream"
    )


# Backward-compatibility alias
RazorpayDocumentResponse = RazorpayDocumentMetadataResponse


# --------------------------------------------------------------------------
# Task 3.1 — Read-only Razorpay Dispute API response schemas
#
# These validate external Razorpay API responses into typed internal models.
# The 'evidence' object is deliberately EXCLUDED from this schema.
# Document retrieval is out of scope for Task 3.1.
# --------------------------------------------------------------------------

# Known Razorpay dispute statuses (from official API docs: api/disputes/entity)
RAZORPAY_DISPUTE_STATUSES = {"open", "under_review", "action_required", "won", "lost", "closed"}

# Known Razorpay dispute phases
RAZORPAY_DISPUTE_PHASES = {
    "fraud", "retrieval", "chargeback", "pre_arbitration", "arbitration"
}


class RazorpayDisputeResponse(BaseModel):
    """
    Internal typed schema for a single Razorpay dispute.

    Validated from external Razorpay API JSON responses.
    The 'evidence' field is deliberately excluded for Task 3.1.
    """

    id: str = Field(
        ...,
        min_length=1,
        description="Razorpay dispute ID e.g. disp_AHfqOvkldwsbqt",
    )
    entity: Literal["dispute"] = Field(
        ...,
        description="Must be 'dispute' — validates correct entity type",
    )
    payment_id: str = Field(..., min_length=1, description="Associated payment ID")
    amount: int = Field(..., ge=0, description="Disputed amount in paise (minor units)")
    currency: str = Field(..., min_length=1, description="Currency code e.g. INR")
    amount_deducted: int = Field(
        ..., ge=0, description="Amount already deducted in paise"
    )
    reason_code: str = Field(..., description="Dispute reason code e.g. chargeback")
    reason_description: Optional[str] = Field(
        default=None, description="Human-readable reason description"
    )
    respond_by: Optional[int] = Field(
        default=None, description="Unix timestamp deadline for response"
    )
    status: str = Field(..., description="Dispute status")
    phase: Optional[str] = Field(default=None, description="Dispute phase")
    created_at: int = Field(..., description="Unix timestamp of creation")
    evidence: Optional[dict] = Field(
        default=None, description="Optional raw evidence payload dictionary"
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in RAZORPAY_DISPUTE_STATUSES:
            raise ValueError(
                f"Unknown dispute status '{v}'. "
                f"Expected one of: {sorted(RAZORPAY_DISPUTE_STATUSES)}"
            )
        return v

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, v: str | None) -> str | None:
        if v is not None and v not in RAZORPAY_DISPUTE_PHASES:
            raise ValueError(
                f"Unknown dispute phase '{v}'. "
                f"Expected one of: {sorted(RAZORPAY_DISPUTE_PHASES)}"
            )
        return v

    model_config = {"extra": "ignore"}


class RazorpayDisputeListResponse(BaseModel):
    """
    Internal typed schema for a paginated list of Razorpay disputes.
    """

    entity: Literal["collection"] = Field(
        ...,
        description="Must be 'collection' — validates correct response type",
    )
    count: int = Field(..., ge=0, description="Number of items in this page")
    items: List[RazorpayDisputeResponse] = Field(
        ..., description="List of dispute entities"
    )

    model_config = {"extra": "ignore"}
