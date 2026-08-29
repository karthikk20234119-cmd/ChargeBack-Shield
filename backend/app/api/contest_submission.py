"""
Contest Submission API Router — Chargeback Shield Task 5.4B

Provides the single controlled contest submission API endpoint:
POST /api/disputes/{dispute_id}/contest-submission

Enforces empty body payload validation to prevent client-injected parameters.
All payload parameters are derived internally from trusted database records.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.contest_submission import (
    ContestSubmissionApiRequest,
    ContestSubmissionResponse,
)
from backend.app.services.contest_submission_service import (
    SubmissionAuthorizationException,
    SubmissionConflictException,
    submit_dispute_contest,
)

logger = logging.getLogger(__name__)

contest_submission_router = APIRouter(prefix="/api/disputes", tags=["contest-submission"])


@contest_submission_router.post(
    "/{dispute_id}/contest-submission",
    response_model=ContestSubmissionResponse,
    status_code=status.HTTP_200_OK,
)
async def execute_contest_submission(
    dispute_id: str,
    body: ContestSubmissionApiRequest = ContestSubmissionApiRequest(),
    db: AsyncSession = Depends(get_db),
) -> ContestSubmissionResponse:
    """
    Executes controlled Razorpay contest submission for an authorized dispute.
    Accepts an empty request body ({}); all parameters are derived internally from local DB state.
    """
    try:
        res = await submit_dispute_contest(dispute_id, db)
        return res
    except SubmissionAuthorizationException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": exc.message,
                "reasons": exc.reasons,
            },
        )
    except SubmissionConflictException as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        )
    except Exception as exc:
        logger.error("Unexpected error executing contest submission: dispute_id=%s, error=%s", dispute_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error executing contest submission: {str(exc)}",
        )
