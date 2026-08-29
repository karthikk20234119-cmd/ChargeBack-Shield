"""
Dispute Lifecycle Dashboard API Router — Chargeback Shield Task 6.1

Provides strictly read-only GET endpoints for operational dashboard monitoring:
- GET /api/dashboard/summary
- GET /api/dashboard/disputes
- GET /api/dashboard/disputes/{dispute_id}
- GET /api/dashboard/alerts
- GET /api/dashboard/reconciliation-required
- GET /api/dashboard/action-required
- GET /api/dashboard/outcomes

SAFETY INVARIANT:
Endpoints are GET only. No mutation endpoints exist. Zero Razorpay network calls executed.
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.dashboard import (
    ActionRequiredItem,
    DashboardSummary,
    DisputeDashboardDetail,
    DisputeListResponse,
    OperationalAlert,
    OutcomeSummary,
    ReconciliationRequiredItem,
)
from backend.app.services.dashboard_service import (
    DashboardException,
    get_action_required_disputes,
    get_dashboard_alerts,
    get_dashboard_disputes,
    get_dashboard_summary,
    get_dispute_dashboard_detail,
    get_outcomes_summary,
    get_reconciliation_required_disputes,
)

logger = logging.getLogger(__name__)

dashboard_router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@dashboard_router.get(
    "/summary",
    response_model=DashboardSummary,
    status_code=status.HTTP_200_OK,
)
async def fetch_dashboard_summary(
    db: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    """Returns aggregated operational summary metrics across all local dispute records."""
    return await get_dashboard_summary(db)


@dashboard_router.get(
    "/disputes",
    response_model=DisputeListResponse,
    status_code=status.HTTP_200_OK,
)
async def fetch_dashboard_disputes(
    status_filter: Optional[str] = Query(None, alias="status"),
    policy_outcome: Optional[str] = Query(None, alias="policy_outcome"),
    review_status: Optional[str] = Query(None, alias="review_status"),
    preflight_status: Optional[str] = Query(None, alias="preflight_status"),
    submission_status: Optional[str] = Query(None, alias="submission_status"),
    lifecycle_status: Optional[str] = Query(None, alias="lifecycle_status"),
    outcome: Optional[str] = Query(None, alias="outcome"),
    created_from: Optional[datetime] = Query(None, alias="created_from"),
    created_to: Optional[datetime] = Query(None, alias="created_to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> DisputeListResponse:
    """Returns a paginated, safely filtered list of disputes for the dashboard."""
    return await get_dashboard_disputes(
        db=db,
        status=status_filter,
        policy_outcome=policy_outcome,
        review_status=review_status,
        preflight_status=preflight_status,
        submission_status=submission_status,
        lifecycle_status=lifecycle_status,
        outcome=outcome,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )


@dashboard_router.get(
    "/disputes/{dispute_id}",
    response_model=DisputeDashboardDetail,
    status_code=status.HTTP_200_OK,
)
async def fetch_dispute_dashboard_detail(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> DisputeDashboardDetail:
    """Returns a 360-degree observability view for a single dispute."""
    try:
        return await get_dispute_dashboard_detail(dispute_id, db)
    except DashboardException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@dashboard_router.get(
    "/alerts",
    response_model=List[OperationalAlert],
    status_code=status.HTTP_200_OK,
)
async def fetch_dashboard_alerts(
    db: AsyncSession = Depends(get_db),
) -> List[OperationalAlert]:
    """Returns active operational alerts across all disputes."""
    return await get_dashboard_alerts(db)


@dashboard_router.get(
    "/reconciliation-required",
    response_model=List[ReconciliationRequiredItem],
    status_code=status.HTTP_200_OK,
)
async def fetch_reconciliation_required(
    db: AsyncSession = Depends(get_db),
) -> List[ReconciliationRequiredItem]:
    """Returns disputes requiring status reconciliation (UNKNOWN state)."""
    return await get_reconciliation_required_disputes(db)


@dashboard_router.get(
    "/action-required",
    response_model=List[ActionRequiredItem],
    status_code=status.HTTP_200_OK,
)
async def fetch_action_required(
    db: AsyncSession = Depends(get_db),
) -> List[ActionRequiredItem]:
    """Returns disputes requiring merchant action on Razorpay."""
    return await get_action_required_disputes(db)


@dashboard_router.get(
    "/outcomes",
    response_model=OutcomeSummary,
    status_code=status.HTTP_200_OK,
)
async def fetch_outcomes_summary(
    db: AsyncSession = Depends(get_db),
) -> OutcomeSummary:
    """Returns breakdown summary of final dispute outcomes across all disputes."""
    return await get_outcomes_summary(db)
