"""
Dispute Lifecycle Synchronization API Router — Chargeback Shield Task 5.5

Provides the controlled dispute lifecycle status synchronization API endpoint:
POST /api/disputes/{dispute_id}/lifecycle/sync

Enforces empty body payload validation to prevent client-injected parameters.
All parameters are derived internally from trusted database records and read-only Razorpay lookup.
ZERO mutation operations exist.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.dispute_lifecycle_sync import (
    DisputeLifecycleSyncApiRequest,
    DisputeLifecycleSyncResponse,
)
from backend.app.services.dispute_lifecycle_sync_service import (
    DisputeLifecycleSyncException,
    sync_dispute_lifecycle,
)

logger = logging.getLogger(__name__)

dispute_lifecycle_sync_router = APIRouter(prefix="/api/disputes", tags=["dispute-lifecycle-sync"])


@dispute_lifecycle_sync_router.post(
    "/{dispute_id}/lifecycle/sync",
    response_model=DisputeLifecycleSyncResponse,
    status_code=status.HTTP_200_OK,
)
async def execute_dispute_lifecycle_sync(
    dispute_id: str,
    body: DisputeLifecycleSyncApiRequest = DisputeLifecycleSyncApiRequest(),
    db: AsyncSession = Depends(get_db),
) -> DisputeLifecycleSyncResponse:
    """
    Synchronizes the latest Razorpay dispute lifecycle state into local Chargeback Shield snapshot records.
    Accepts an empty request body ({}); all parameters are derived internally from trusted local DB state.
    """
    try:
        res = await sync_dispute_lifecycle(dispute_id, db)
        return res
    except DisputeLifecycleSyncException as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        )
    except Exception as exc:
        logger.error("Unexpected error executing dispute lifecycle sync: dispute_id=%s, error=%s", dispute_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error executing dispute lifecycle sync: {str(exc)}",
        )
