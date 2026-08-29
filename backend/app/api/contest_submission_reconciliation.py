"""
Contest Submission Reconciliation API Router — Chargeback Shield Task 5.4C

Provides the single controlled contest submission status reconciliation API endpoint:
POST /api/disputes/{dispute_id}/contest-submission/reconcile

Enforces empty body payload validation to prevent client-injected parameters.
All parameters are derived internally from trusted database records.
Uses strictly read-only Razorpay dispute lookup. ZERO mutation operations exist.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.contest_submission_reconciliation import (
    ContestSubmissionReconcileApiRequest,
    ContestSubmissionReconciliationResponse,
)
from backend.app.services.contest_submission_reconciliation_service import (
    SubmissionReconciliationException,
    reconcile_contest_submission,
)

logger = logging.getLogger(__name__)

contest_submission_reconciliation_router = APIRouter(prefix="/api/disputes", tags=["contest-submission-reconciliation"])


@contest_submission_reconciliation_router.post(
    "/{dispute_id}/contest-submission/reconcile",
    response_model=ContestSubmissionReconciliationResponse,
    status_code=status.HTTP_200_OK,
)
async def execute_contest_submission_reconciliation(
    dispute_id: str,
    body: ContestSubmissionReconcileApiRequest = ContestSubmissionReconcileApiRequest(),
    db: AsyncSession = Depends(get_db),
) -> ContestSubmissionReconciliationResponse:
    """
    Reconciles a local contest submission record against read-only Razorpay dispute status.
    Accepts an empty request body ({}); all parameters are derived internally from local DB state.
    """
    try:
        res = await reconcile_contest_submission(dispute_id, db)
        return res
    except SubmissionReconciliationException as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        )
    except Exception as exc:
        logger.error("Unexpected error executing contest submission reconciliation: dispute_id=%s, error=%s", dispute_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error executing contest submission reconciliation: {str(exc)}",
        )
