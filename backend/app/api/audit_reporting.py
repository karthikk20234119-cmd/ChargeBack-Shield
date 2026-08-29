"""
Audit & Compliance Reporting API Router — Chargeback Shield Task 6.2

Provides strictly read-only GET endpoints for audit & compliance reporting:
- GET /api/audit/disputes/{dispute_id}/timeline
- GET /api/audit/disputes/{dispute_id}/traceability
- GET /api/audit/disputes/{dispute_id}/policy-report
- GET /api/audit/disputes/{dispute_id}/review-report
- GET /api/audit/disputes/{dispute_id}/submission-report
- GET /api/audit/disputes/{dispute_id}/financial-integrity
- GET /api/audit/disputes/{dispute_id}/security-report
- GET /api/audit/disputes/{dispute_id}/export

SAFETY INVARIANT:
Endpoints are GET only. No mutation endpoints exist. Zero Razorpay network calls executed.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.audit_reporting import (
    ComplianceExport,
    DisputeAuditTimeline,
    DisputeTraceabilityReport,
    FinancialIntegrityReport,
    HumanReviewAuditReport,
    PolicyComplianceReport,
    SecurityAuditReport,
    SubmissionAuditReport,
)
from backend.app.services.audit_reporting_service import (
    AuditReportingException,
    generate_compliance_export,
    get_dispute_audit_timeline,
    get_dispute_traceability_graph,
    get_financial_integrity_report,
    get_human_review_audit_report,
    get_policy_compliance_report,
    get_security_audit_report,
    get_submission_audit_report,
)

logger = logging.getLogger(__name__)

audit_reporting_router = APIRouter(prefix="/api/audit/disputes", tags=["audit-reporting"])


@audit_reporting_router.get(
    "/{dispute_id}/timeline",
    response_model=DisputeAuditTimeline,
    status_code=status.HTTP_200_OK,
)
async def fetch_dispute_audit_timeline(
    dispute_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> DisputeAuditTimeline:
    """Returns a chronological, paginated audit timeline for a dispute."""
    try:
        return await get_dispute_audit_timeline(dispute_id, db, page=page, page_size=page_size)
    except AuditReportingException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@audit_reporting_router.get(
    "/{dispute_id}/traceability",
    response_model=DisputeTraceabilityReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_dispute_traceability(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> DisputeTraceabilityReport:
    """Returns a directed acyclic graph (DAG) traceability report for a dispute."""
    try:
        return await get_dispute_traceability_graph(dispute_id, db)
    except AuditReportingException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@audit_reporting_router.get(
    "/{dispute_id}/policy-report",
    response_model=PolicyComplianceReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_policy_compliance_report(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> PolicyComplianceReport:
    """Reads persisted PolicyResult and rule compliance metrics without running policy engine."""
    return await get_policy_compliance_report(dispute_id, db)


@audit_reporting_router.get(
    "/{dispute_id}/review-report",
    response_model=HumanReviewAuditReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_human_review_report(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> HumanReviewAuditReport:
    """Reads draft review history and review audit trail."""
    return await get_human_review_audit_report(dispute_id, db)


@audit_reporting_router.get(
    "/{dispute_id}/submission-report",
    response_model=SubmissionAuditReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_submission_report(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> SubmissionAuditReport:
    """Reads submission attempt history and submission audit trail."""
    return await get_submission_audit_report(dispute_id, db)


@audit_reporting_router.get(
    "/{dispute_id}/financial-integrity",
    response_model=FinancialIntegrityReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_financial_integrity_report(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> FinancialIntegrityReport:
    """Verifies historical payment_id, amount, currency against trusted values."""
    try:
        return await get_financial_integrity_report(dispute_id, db)
    except AuditReportingException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@audit_reporting_router.get(
    "/{dispute_id}/security-report",
    response_model=SecurityAuditReport,
    status_code=status.HTTP_200_OK,
)
async def fetch_security_report(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> SecurityAuditReport:
    """Aggregates recorded security audit findings."""
    return await get_security_audit_report(dispute_id, db)


@audit_reporting_router.get(
    "/{dispute_id}/export",
    response_model=ComplianceExport,
    status_code=status.HTTP_200_OK,
)
async def fetch_compliance_export(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
) -> ComplianceExport:
    """Generates a structured JSON compliance export and calculates canonical SHA-256 report hash."""
    try:
        return await generate_compliance_export(dispute_id, db)
    except AuditReportingException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
