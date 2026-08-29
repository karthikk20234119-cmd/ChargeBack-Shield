from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class BoundingBox(BaseModel):
    box_2d: List[int] = Field(description="[ymin, xmin, ymax, xmax]")
    text_content: Optional[str] = None

class ExtractedEvidenceSchema(BaseModel):
    document_type: str = Field(default="shipping_proof", description="Razorpay proof category")
    dispute_id: Optional[str] = None
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    awb_number: Optional[str] = None
    courier_name: Optional[str] = None
    customer_name: Optional[str] = None
    shipping_address: Optional[str] = None
    invoice_amount: Optional[float] = Field(default=None, description="Amount extracted from document in major units (e.g. 5000.00)")
    currency: Optional[str] = Field(default="INR", description="Extracted currency ISO code")
    delivery_date: Optional[str] = Field(default=None, description="ISO format delivery date")
    signature_present: bool = Field(default=False, description="Whether delivery signature or proof is visible")
    confidence_score: float = Field(default=0.0, description="Vision LLM confidence score 0.0 to 1.0")
    bounding_boxes: Optional[Dict[str, BoundingBox]] = Field(default=None, description="Entity bounding box map")

class DocumentUploadResponse(BaseModel):
    evidence_id: str
    dispute_id: str
    filename: str
    mime_type: str
    file_size: int
    sha256: str
    status: str = "UPLOADED"
