import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base

class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True) # Razorpay dispute_id e.g. disp_123
    entity: Mapped[str] = mapped_column(String(32), default="dispute")
    payment_id: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[int] = mapped_column(Integer) # In paise/minor units
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    amount_deducted: Mapped[int] = mapped_column(Integer, default=0)
    
    reason_code: Mapped[str] = mapped_column(String(32), index=True) # e.g. 13.1
    reason_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    status: Mapped[str] = mapped_column(String(32), index=True) # open, under_review, won, lost, closed
    phase: Mapped[Optional[str]] = mapped_column(String(32), nullable=True) # fraud, retrieval, chargeback, pre_arbitration
    respond_by: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_contact: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    documents: Mapped[List["EvidenceDocument"]] = relationship("EvidenceDocument", back_populates="dispute", cascade="all, delete-orphan")
    match_results: Mapped[List["MatchResult"]] = relationship("MatchResult", back_populates="dispute", cascade="all, delete-orphan")
    policy_results: Mapped[List["PolicyResult"]] = relationship("PolicyResult", back_populates="dispute", cascade="all, delete-orphan")
    contest_drafts: Mapped[List["ContestDraft"]] = relationship("ContestDraft", back_populates="dispute", cascade="all, delete-orphan")
    preflights: Mapped[List["ContestSubmissionPreflight"]] = relationship("ContestSubmissionPreflight", back_populates="dispute", cascade="all, delete-orphan")
    submissions: Mapped[List["ContestSubmission"]] = relationship("ContestSubmission", back_populates="dispute", cascade="all, delete-orphan")
    submission_audits: Mapped[List["ContestSubmissionAudit"]] = relationship("ContestSubmissionAudit", back_populates="dispute", cascade="all, delete-orphan")
    lifecycle_snapshots: Mapped[List["DisputeLifecycleSnapshot"]] = relationship("DisputeLifecycleSnapshot", back_populates="dispute", cascade="all, delete-orphan")
    operational_alerts: Mapped[List["OperationalAlert"]] = relationship("OperationalAlert", back_populates="dispute", cascade="all, delete-orphan")

