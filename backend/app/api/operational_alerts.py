"""
Operational Alerts, SLA Monitoring & Exception Management API Router — Chargeback Shield Task 6.3

Provides operational endpoints:
- GET /api/operations/alerts/summary
- GET /api/operations/alerts
- GET /api/operations/disputes/{dispute_id}/alerts
- GET /api/operations/sla
- GET /api/operations/exceptions
- GET /api/operations/health
- POST /api/operations/alerts/detect
- POST /api/operations/alerts/{alert_id}/acknowledge

SAFETY INVARIANT:
Alert endpoints consume persisted local database state exclusively.
ZERO Razorpay network calls or external AI/LLM calls are executed.
Source business entities are NEVER mutated.
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.operational_alert import (
    AlertCategory,
    AlertDetectionRequest,
    AlertDetectionResult,
    AlertSeverity,
    AlertStatus,
    DisputeAlertDetail,
    OperationalAlert,
    OperationalAlertSummary,
    OperationalExceptionReport,
    OperationalHealthReport,
    SLAMonitoringReport,
)
from backend.app.schemas.dashboard import (
    ActionRequiredItem,
    ReconciliationRequiredItem,
)
from backend.app.services.dashboard_service import (
    get_action_required_disputes,
    get_reconciliation_required_disputes,
)
from backend.app.services.operational_alert_service import (
    OperationalAlertException,
    acknowledge_operational_alert,
    detect_operational_alerts,
    get_alerts_summary,
    get_dispute_alert_detail,
    get_filtered_alerts,
    get_operational_exceptions_report,
    get_operational_health_report,
    get_sla_monitoring_report,
)

logger = logging.getLogger(__name__)

operational_alerts_router = APIRouter(prefix="/api/operations", tags=["operational-alerts"])


@operational_alerts_router.get(
    "/alerts/summary",
    response_model=OperationalAlertSummary,
    status_code=status.HTTP_200_OK,
)
async def fetch_alerts_summary(
    db: AsyncSession = Depends(get_db),
) -> OperationalAlertSummary:
    """Returns aggregated summary counts of active operational alerts."""
    return await get_alerts_summary(db)


@operational_alerts_router.get(
    "/alerts",
    response_model=List[OperationalAlert],
    status_code=status.HTTP_200_OK,
)
async def fetch_filtered_alerts(
    alert_status: Optional[AlertStatus] = Query(None, alias="status"),
    severity: Optional[AlertSeverity] = Query(None),
    category: Optional[AlertCategory] = Query(None),
    dispute_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[OperationalAlert]:
    """Returns filtered, paginated operational alerts with hardcoded deterministic sorting."""
    status_str = alert_status.value if alert_status else None
    severity_str = severity.value if severity else None
    category_str = category.value if category else None

    alerts, _ = await get_filtered_alerts(
        db=db,
        status=status_str,
        severity=severity_str,
        category=category_str,
        dispute_id=dispute_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return alerts


@operational_alerts_router.get(
    "/disputes/{dispute_id}/alerts",
    response_model=DisputeAlertDetail,
    status_code=status.HTTP_200_OK,
)
async def fetch_dispute_alert_detail(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> DisputeAlertDetail:
    """Returns alert detail and history for a specific dispute."""
    return await get_dispute_alert_detail(dispute_id, db)


@operational_alerts_router.get(
    "/sla",
    response_model=SLAMonitoringReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_sla_monitoring_report(
    db: AsyncSession = Depends(get_db),
) -> SLAMonitoringReport:
    """Calculates SLA metrics across all tracked operational items."""
    return await get_sla_monitoring_report(db)


@operational_alerts_router.get(
    "/exceptions",
    response_model=OperationalExceptionReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_operational_exceptions_report(
    db: AsyncSession = Depends(get_db),
) -> OperationalExceptionReport:
    """Aggregates operational exceptions by severity and domain category."""
    return await get_operational_exceptions_report(db)


@operational_alerts_router.get(
    "/health",
    response_model=OperationalHealthReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_operational_health_report(
    db: AsyncSession = Depends(get_db),
) -> OperationalHealthReport:
    """Calculates high-level system health metrics from persisted records."""
    return await get_operational_health_report(db)


@operational_alerts_router.post(
    "/alerts/detect",
    response_model=AlertDetectionResult,
    status_code=status.HTTP_200_OK,
)
async def trigger_alert_detection(
    request_body: AlertDetectionRequest,
    db: AsyncSession = Depends(get_db),
) -> AlertDetectionResult:
    """
    Triggers local alert detection over persisted database records.
    Requires empty body `{}`.
    MUST NOT call Razorpay or mutate source business entities.
    """
    return await detect_operational_alerts(db)


@operational_alerts_router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=OperationalAlert,
    status_code=status.HTTP_200_OK,
)
async def acknowledge_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
) -> OperationalAlert:
    """Modifies ONLY OperationalAlert.status to ACKNOWLEDGED. Does NOT mutate dispute state."""
    try:
        return await acknowledge_operational_alert(alert_id, db)
    except OperationalAlertException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@operational_alerts_router.get(
    "/action-required",
    response_model=List[ActionRequiredItem],
    status_code=status.HTTP_200_OK,
)
async def fetch_action_required_disputes_op(
    db: AsyncSession = Depends(get_db),
) -> List[ActionRequiredItem]:
    """Returns disputes requiring operational action."""
    return await get_action_required_disputes(db)


@operational_alerts_router.get(
    "/reconciliation-required",
    response_model=List[ReconciliationRequiredItem],
    status_code=status.HTTP_200_OK,
)
async def fetch_reconciliation_required_disputes_op(
    db: AsyncSession = Depends(get_db),
) -> List[ReconciliationRequiredItem]:
    """Returns disputes with UNKNOWN submission state requiring status reconciliation."""
    return await get_reconciliation_required_disputes(db)

