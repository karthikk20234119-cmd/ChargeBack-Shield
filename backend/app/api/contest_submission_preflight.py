"""
Contest Submission Preflight API Endpoint — Chargeback Shield Task 5.3

Provides local preflight authorization check endpoint.
LOCAL ONLY. ZERO Razorpay mutation. ZERO AI/LLM calls.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.contest_submission_preflight import ContestSubmissionPreflightResult
from backend.app.services.contest_submission_preflight_service import (
    StaleDraftException,
    run_preflight,
)

router = APIRouter(tags=["Contest Submission Preflight Gate"])


@router.post(
    "/api/disputes/{dispute_id}/contest-submission/preflight",
    response_model=ContestSubmissionPreflightResult,
    status_code=status.HTTP_200_OK,
    summary="Execute deterministic local contest submission preflight authorization check",
)
async def run_contest_submission_preflight_endpoint(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> ContestSubmissionPreflightResult:
    """
    Executes a deterministic local preflight authorization check for a local ContestDraft.
    Request body MUST BE EMPTY. All inputs are derived from DB state.
    LOCAL ONLY. ZERO Razorpay calls. ZERO external network calls.
    """
    try:
        preflight_res = await run_preflight(
            dispute_id=dispute_id,
            db=db,
        )
        return preflight_res
    except StaleDraftException as sde:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(sde))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ex))
