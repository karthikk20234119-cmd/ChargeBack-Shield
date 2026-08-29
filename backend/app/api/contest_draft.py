from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.contest_draft import ContestDraft
from backend.app.schemas.contest_draft_review import ContestDraftReviewRequest, ContestDraftReviewResponse
from backend.app.services.contest_draft_review_service import (
    ConflictTransitionException,
    InvalidTransitionException,
    StaleDraftException,
    get_latest_draft_schema,
    review_contest_draft,
)
from backend.app.services.contest_draft_service import generate_contest_draft

router = APIRouter(tags=["Contest Response Drafting Engine"])


@router.post(
    "/api/disputes/{dispute_id}/generate-contest-draft",
    response_model=ContestDraft,
    status_code=status.HTTP_200_OK,
    summary="Generate human-reviewable contest response draft (DRAFT ONLY)",
)
async def generate_contest_draft_endpoint(
    dispute_id: str,
    reference_date: str = Query("2026-08-26", description="ISO reference date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> ContestDraft:
    """
    Generates a structured, explainable, human-reviewable ContestDraft.
    The client provides ONLY the dispute_id path identifier.
    ZERO Razorpay mutation calls. ZERO automated dispute submission.
    """
    try:
        draft = await generate_contest_draft(
            dispute_id=dispute_id,
            db=db,
            reference_date=reference_date,
        )
        return draft
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ex))


@router.get(
    "/api/disputes/{dispute_id}/contest-draft",
    response_model=ContestDraft,
    status_code=status.HTTP_200_OK,
    summary="Retrieve latest local contest response draft",
)
async def get_latest_contest_draft_endpoint(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> ContestDraft:
    """
    Retrieves the latest local ContestDraft for a dispute.
    Returns status and review_status without making external API calls.
    """
    try:
        draft = await get_latest_draft_schema(dispute_id=dispute_id, db=db)
        return draft
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ex))


@router.post(
    "/api/disputes/{dispute_id}/contest-draft/review",
    response_model=ContestDraftReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Review (Approve/Reject) local contest response draft (LOCAL ONLY)",
)
async def review_contest_draft_endpoint(
    dispute_id: str,
    body: ContestDraftReviewRequest,
    db: AsyncSession = Depends(get_db),
) -> ContestDraftReviewResponse:
    """
    Executes local human review (APPROVE or REJECT) for a ContestDraft.
    The client provides ONLY dispute_id path identifier, decision, comment, and reviewer_reference.
    LOCAL ONLY. ZERO Razorpay calls. ZERO AI calls.
    """
    try:
        res = await review_contest_draft(
            dispute_id=dispute_id,
            decision=body.decision,
            comment=body.comment,
            reviewer_reference=body.reviewer_reference or "merchant_admin",
            db=db,
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except InvalidTransitionException as ite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ite))
    except StaleDraftException as sde:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(sde))
    except ConflictTransitionException as cte:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(cte))
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ex))
