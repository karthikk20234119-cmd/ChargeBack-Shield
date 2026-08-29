"""
Dispute Analytics, Management Reporting & Performance Insights API Router — Chargeback Shield Task 6.4

Provides strictly read-only GET endpoints:
- GET /api/analytics/summary
- GET /api/analytics/outcomes
- GET /api/analytics/evidence
- GET /api/analytics/matching
- GET /api/analytics/policy
- GET /api/analytics/drafts
- GET /api/analytics/submissions
- GET /api/analytics/operations
- GET /api/analytics/sla
- GET /api/analytics/funnel
- GET /api/analytics/bottlenecks
- GET /api/analytics/failures
- GET /api/analytics/security
- GET /api/analytics/financial-integrity
- GET /api/analytics/export

SAFETY INVARIANT:
Endpoints are GET only. No mutation endpoints exist. Zero Razorpay network calls executed.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.analytics import (
    AnalyticsExport,
    BottleneckAnalysisReport,
    DisputeOutcomeAnalytics,
    DraftAnalytics,
    EvidenceAnalytics,
    FailureAnalyticsReport,
    FinancialIntegrityAnalyticsReport,
    LifecycleFunnelReport,
    ManagementAnalyticsSummary,
    MatchingAnalytics,
    OperationalAnalytics,
    OutcomeAnalyticsReport,
    PolicyAnalytics,
    SecurityComplianceAnalyticsReport,
    SubmissionAnalytics,
    TimeRangeEnum,
)
from backend.app.services.analytics_service import (
    AnalyticsException,
    generate_analytics_export,
    get_bottleneck_analysis,
    get_draft_analytics,
    get_evidence_analytics,
    get_failure_analytics,
    get_financial_integrity_analytics,
    get_lifecycle_funnel,
    get_management_summary,
    get_matching_analytics,
    get_operational_analytics,
    get_outcome_analytics,
    get_policy_analytics,
    get_security_analytics,
    get_sla_analytics,
    get_submission_analytics,
    resolve_date_range,
)

logger = logging.getLogger(__name__)

analytics_router = APIRouter(prefix="/api/analytics", tags=["analytics-reporting"])


@analytics_router.get(
    "/summary",
    response_model=ManagementAnalyticsSummary,
    status_code=status.HTTP_200_OK,
)
async def fetch_management_summary(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> ManagementAnalyticsSummary:
    """Returns high-level executive summary metrics across all dispute stages."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_management_summary(db, start_dt, end_dt)


@analytics_router.get(
    "/outcomes",
    response_model=OutcomeAnalyticsReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_outcome_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    db: AsyncSession = Depends(get_db),
) -> OutcomeAnalyticsReport:
    """Calculates outcome distribution metrics and optional period trend aggregation."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_outcome_analytics(db, start_dt, end_dt, period=period)


@analytics_router.get(
    "/evidence",
    response_model=EvidenceAnalytics,
    status_code=status.HTTP_200_OK,
)
async def fetch_evidence_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> EvidenceAnalytics:
    """Calculates evidence document processing and completeness analytics."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_evidence_analytics(db, start_dt, end_dt)


@analytics_router.get(
    "/matching",
    response_model=MatchingAnalytics,
    status_code=status.HTTP_200_OK,
)
async def fetch_matching_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> MatchingAnalytics:
    """Calculates fact matching evaluation analytics across all match results."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_matching_analytics(db, start_dt, end_dt)


@analytics_router.get(
    "/policy",
    response_model=PolicyAnalytics,
    status_code=status.HTTP_200_OK,
)
async def fetch_policy_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PolicyAnalytics:
    """Calculates policy engine decision and eligibility analytics."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_policy_analytics(db, start_dt, end_dt)


@analytics_router.get(
    "/drafts",
    response_model=DraftAnalytics,
    status_code=status.HTTP_200_OK,
)
async def fetch_draft_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> DraftAnalytics:
    """Calculates contest draft status and review approval analytics."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_draft_analytics(db, start_dt, end_dt)


@analytics_router.get(
    "/submissions",
    response_model=SubmissionAnalytics,
    status_code=status.HTTP_200_OK,
)
async def fetch_submission_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> SubmissionAnalytics:
    """Calculates contest submission state and failure distribution analytics."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_submission_analytics(db, start_dt, end_dt)


@analytics_router.get(
    "/operations",
    response_model=OperationalAnalytics,
    status_code=status.HTTP_200_OK,
)
async def fetch_operational_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> OperationalAnalytics:
    """Calculates operational alert distribution and status analytics."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_operational_analytics(db, start_dt, end_dt)


@analytics_router.get(
    "/sla",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def fetch_sla_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Calculates SLA compliance percentage and average resolution timing metrics."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_sla_analytics(db, start_dt, end_dt)


@analytics_router.get(
    "/funnel",
    response_model=LifecycleFunnelReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_lifecycle_funnel(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> LifecycleFunnelReport:
    """Calculates deterministic conversion and drop-off metrics across the 12 lifecycle stages."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_lifecycle_funnel(db, start_dt, end_dt)


@analytics_router.get(
    "/bottlenecks",
    response_model=BottleneckAnalysisReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_bottleneck_analysis(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> BottleneckAnalysisReport:
    """Identifies pipeline stages with highest drop-off, pending reviews, or failures."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_bottleneck_analysis(db, start_dt, end_dt)


@analytics_router.get(
    "/failures",
    response_model=FailureAnalyticsReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_failure_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> FailureAnalyticsReport:
    """Aggregates failure metrics across all pipeline stages."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_failure_analytics(db, start_dt, end_dt)


@analytics_router.get(
    "/security",
    response_model=SecurityComplianceAnalyticsReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_security_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> SecurityComplianceAnalyticsReport:
    """Aggregates security audit findings recorded across audit tables and alert records."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_security_analytics(db, start_dt, end_dt)


@analytics_router.get(
    "/financial-integrity",
    response_model=FinancialIntegrityAnalyticsReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_financial_integrity_analytics(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> FinancialIntegrityAnalyticsReport:
    """Verifies historical payment_id, amount, and currency integrity across disputes."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await get_financial_integrity_analytics(db, start_dt, end_dt)


@analytics_router.get(
    "/export",
    response_model=AnalyticsExport,
    status_code=status.HTTP_200_OK,
)
async def fetch_analytics_export(
    time_range: Optional[TimeRangeEnum] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsExport:
    """Generates structured JSON analytics export and calculates canonical SHA-256 report hash."""
    start_dt, end_dt = resolve_date_range(time_range.value if time_range else None, date_from, date_to)
    return await generate_analytics_export(db, start_dt, end_dt)
