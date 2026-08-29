import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base

class ProcessedArtifact(Base):
    __tablename__ = "processed_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evidence_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    file_path: Mapped[str] = mapped_column(String(512))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(16), default="PNG")
    source_document_type: Mapped[str] = mapped_column(String(32))
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    document: Mapped["EvidenceDocument"] = relationship("EvidenceDocument", back_populates="artifacts")
