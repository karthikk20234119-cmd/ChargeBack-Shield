"""
Structured Fact Extraction Schemas — Phase 4 Task 4.1

Defines Pydantic schemas for extracted evidence facts, confidence metrics,
visual bounding boxes, and provenance metadata.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class EvidenceFactItem(BaseModel):
    """
    Schema for an individual extracted evidence fact with provenance & confidence.
    """

    category: Literal[
        "TRANSACTION",
        "CUSTOMER",
        "SHIPPING",
        "INVOICE",
        "REFUND",
        "COMMUNICATION",
        "SERVICE",
        "POLICY",
    ] = Field(..., description="Fact category domain")
    field_name: str = Field(..., description="Name of extracted fact field e.g. amount, delivery_date")
    field_value: Optional[str] = Field(default=None, description="Raw extracted text value")
    normalized_value: Optional[Any] = Field(default=None, description="Normalized typed value")
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        default="MEDIUM", description="Standardized confidence level"
    )
    extraction_method: str = Field(
        default="ocr", description="Extraction method used: vision, ocr, text"
    )
    source_page: int = Field(default=1, ge=1, description="1-indexed source page number")
    source_region: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional visual bounding box coordinates"
    )
    extractor_version: str = Field(default="1.0", description="Extractor version")


class ExtractedFactSchema(BaseModel):
    """
    Pydantic schema representing the complete structured fact extraction from an evidence document.
    """

    document_type: str = Field(
        default="unknown",
        description="Type of evidence document: invoice, shipping_proof, delivery_proof, or unknown",
    )
    payment_id: Optional[str] = Field(default=None, description="Razorpay payment ID e.g. pay_XXXXX")
    order_id: Optional[str] = Field(default=None, description="Merchant order ID e.g. ord_XXXXX")
    amount_minor: Optional[int] = Field(
        default=None, description="Extracted currency amount in minor integer units (paise/cents)"
    )
    currency: Optional[str] = Field(default="INR", description="ISO 4217 currency code")
    customer_name: Optional[str] = Field(default=None, description="Customer or consignee full name")
    merchant_name: Optional[str] = Field(default=None, description="Merchant business name")
    awb_number: Optional[str] = Field(default=None, description="Airway bill / tracking number")
    invoice_date: Optional[str] = Field(default=None, description="ISO format invoice date (YYYY-MM-DD)")
    delivery_date: Optional[str] = Field(default=None, description="ISO format delivery date (YYYY-MM-DD)")
    signature_present: Optional[bool] = Field(
        default=None,
        description="True if delivery signature or OTP proof exists, False if absent, None if unknown",
    )

    facts: List[EvidenceFactItem] = Field(
        default_factory=list, description="List of granular extracted facts with provenance"
    )

    confidence_by_field: Optional[Dict[str, float]] = Field(
        default_factory=dict, description="Field-level log probability scores (0.0 to 1.0)"
    )
    bounding_boxes: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Visual bounding box coordinates per field"
    )
    extraction_warnings: List[str] = Field(
        default_factory=list, description="Uncertainties or unreadable field warnings"
    )

    schema_version: str = Field(default="1.0", description="Extraction schema version")

    @field_validator("document_type")
    @classmethod
    def validate_doc_type(cls, v: str) -> str:
        valid_types = {"invoice", "shipping_proof", "delivery_proof", "unknown"}
        v_clean = (v or "").lower().strip()
        return v_clean if v_clean in valid_types else "unknown"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return "INR"
        return v.upper().strip()
