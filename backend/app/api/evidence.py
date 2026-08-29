from fastapi import APIRouter, Depends, UploadFile, File, status, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.evidence import DocumentUploadResponse
from backend.app.services.evidence_service import process_evidence_upload
from backend.app.services.processing_service import process_evidence_document
from backend.app.services.ai_extraction_service import execute_ai_extraction

router = APIRouter(tags=["Evidence Upload, Processing & AI Extraction"])

@router.post(
    "/api/disputes/{dispute_id}/evidence",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload secure evidence file for a dispute"
)
async def upload_evidence_for_dispute(
    dispute_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Accepts PDF, JPEG, JPG, or PNG evidence file for an existing dispute.
    Validates dispute existence, file size limits, magic bytes, SHA-256 duplicate content, 
    and saves file with a secure UUID internal path.
    """
    result = await process_evidence_upload(
        dispute_id=dispute_id,
        file=file,
        db=db
    )
    return result

@router.post(
    "/api/evidence/{evidence_id}/process",
    status_code=status.HTTP_200_OK,
    summary="Process uploaded evidence into AI-ready PNG page images"
)
async def process_evidence_endpoint(
    evidence_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers rasterization for PDFs or normalization for JPEG/PNG images.
    Converts pages into standardized PNG representations inside storage/processed/{evidence_id}/
    and updates processing_status to READY_FOR_AI or PROCESSING_FAILED.
    """
    result = await process_evidence_document(
        evidence_id=evidence_id,
        db=db
    )
    return result

@router.post(
    "/api/evidence/{evidence_id}/extract",
    status_code=status.HTTP_200_OK,
    summary="Execute AI fact extraction on processed evidence page images"
)
async def extract_evidence_endpoint(
    evidence_id: str,
    document_hint: Optional[str] = Query(None, description="Optional document type hint or test mock scenario"),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes AI fact extraction on READY_FOR_AI processed page images.
    Parses facts into ExtractedFactSchema Pydantic object, persists ExtractedEvidence record,
    and updates processing_status to AI_EXTRACTED.
    Does NOT make financial decisions (ALLOW / REJECT / HUMAN_REVIEW).
    """
    result = await execute_ai_extraction(
        evidence_id=evidence_id,
        db=db,
        document_hint=document_hint
    )
    return result
