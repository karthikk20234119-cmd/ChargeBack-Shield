from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.policy import PolicyEvaluationSummary, PolicyResultSchema
from backend.app.services.policy_engine_service import evaluate_dispute_policy

router = APIRouter(tags=["Deterministic Policy Engine"])


@router.post(
    "/api/disputes/{dispute_id}/evaluate-policy",
    response_model=PolicyResultSchema,
    status_code=status.HTTP_200_OK,
    summary="Evaluate deterministic policy rules and eligibility for a dispute",
)
@router.post(
    "/api/disputes/{dispute_id}/policy/evaluate",
    response_model=PolicyResultSchema,
    status_code=status.HTTP_200_OK,
    summary="Evaluate deterministic policy rules for a dispute (legacy path)",
)
async def evaluate_policy_endpoint(
    dispute_id: str,
    reference_date: str = Query("2026-08-26", description="ISO reference evaluation date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> PolicyResultSchema:
    """
    Evaluates deterministic policy rules for Visa Reason Code 13.1.
    Client provides ONLY the dispute_id path identifier.
    Returns typed PolicyResultSchema.
    Does NOT call OpenAI or Razorpay. Zero automated financial submission.
    """
    try:
        result = await evaluate_dispute_policy(
            dispute_id=dispute_id,
            db=db,
            reference_date=reference_date,
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ex))
