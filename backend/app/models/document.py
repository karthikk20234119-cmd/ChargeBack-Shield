import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, ForeignKey, Float, JSON, Boolean, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base

class EvidenceDocument(Base):
    __tablename__ = "evidence_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id: Mapped[str] = mapped_column(String(64), ForeignKey("disputes.id", ondelete="CASCADE"), index=True)
    razorpay_doc_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    original_filename: Mapped[str] = mapped_column(String(255))
    internal_filename: Mapped[str] = mapped_column(String(255), unique=True)
    file_path: Mapped[str] = mapped_column(String(512))
    file_hash: Mapped[str] = mapped_column(String(64), index=True) # SHA-256 hash
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(64))
    document_type: Mapped[str] = mapped_column(String(64), default="shipping_proof")
    processing_status: Mapped[str] = mapped_column(String(32), default="UPLOADED", index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="documents")
    extraction: Mapped[Optional["ExtractedEvidence"]] = relationship("ExtractedEvidence", back_populates="document", uselist=False, cascade="all, delete-orphan")
    artifacts: Mapped[List["ProcessedArtifact"]] = relationship("ProcessedArtifact", back_populates="document", cascade="all, delete-orphan", order_by="ProcessedArtifact.page_number")


class ExtractedEvidence(Base):
    __tablename__ = "extracted_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_documents.id", ondelete="CASCADE"), unique=True, index=True)
    
    # Structured Fact Extraction Fields
    document_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True) # invoice, shipping_proof, delivery_proof, unknown
    payment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    amount_minor: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True) # Minor units (paise)
    currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    awb_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    delivery_date: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    signature_present: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0) # Average confidence
    confidence_by_field: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    bounding_boxes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    extraction_warnings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    extracted_data: Mapped[dict] = mapped_column(JSON) # Complete validated Pydantic JSON
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Unfiltered model response
    
    # Model Audit Metadata
    model_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    document: Mapped["EvidenceDocument"] = relationship("EvidenceDocument", back_populates="extraction")
