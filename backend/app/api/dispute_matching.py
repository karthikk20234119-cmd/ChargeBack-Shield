"""
Dispute Evidence Matching API Router — Phase 4 Task 4.2

Provides HTTP endpoint for running deterministic evidence matching:
POST /api/disputes/{dispute_id}/match-evidence
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.matching import MatchingRunResult
from backend.app.services.matching_service import run_evidence_matching

router = APIRouter(tags=["Evidence Matching"])


@router.post(
    "/api/disputes/{dispute_id}/match-evidence",
    response_model=MatchingRunResult,
    status_code=status.HTTP_200_OK,
    summary="Execute deterministic evidence matching for a dispute",
)
async def match_dispute_evidence_endpoint(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Compares trusted dispute data against ExtractedEvidence document facts.
    Returns deterministic MatchResult records without making policy, eligibility, or contest decisions.
    """
    try:
        result = await run_evidence_matching(dispute_id=dispute_id, db=db)
        return result
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence matching error: {str(exc)}",
        ) from exc
