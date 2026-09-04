"""
Dispute Synchronization API — Task 3.2

POST /api/disputes/{dispute_id}/sync

Synchronizes a Razorpay dispute with the local database.

FINANCIAL SAFETY:
- This endpoint modifies ONLY the local database
- It NEVER mutates Razorpay (no contest, accept, reject, submit)
- Financial identity conflicts are detected, not auto-overwritten
"""

from __future__ import annotations

import os
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.schemas.evidence_sync import DisputeEvidenceSyncResult
from backend.app.schemas.sync import DisputeSyncResult
from backend.app.services.dispute_sync_service import RazorpayDisputeSyncService
from backend.app.services.razorpay_client import HttpRazorpayClient, MockRazorpayClient
from backend.app.services.razorpay_evidence_sync_service import RazorpayEvidenceSyncService
from backend.app.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/disputes", tags=["dispute-sync"])


def _get_sync_service() -> RazorpayDisputeSyncService:
    """
    Dependency provider for RazorpayDisputeSyncService.

    Uses MockRazorpayClient in test/development when credentials
    are placeholder values; HttpRazorpayClient otherwise.
    """
    is_placeholder = (
        not settings.RAZORPAY_KEY_ID
        or settings.RAZORPAY_KEY_ID.startswith("rzp_test_sample")
        or settings.RAZORPAY_KEY_SECRET == "samplesecretkey123456"
    )

    if settings.ENVIRONMENT in ("test", "testing") or "PYTEST_CURRENT_TEST" in os.environ or is_placeholder:
        client = MockRazorpayClient()
    else:
        client = HttpRazorpayClient(settings)

    razorpay_service = RazorpayService(client=client)
    return RazorpayDisputeSyncService(razorpay_service=razorpay_service)


def _get_evidence_sync_service() -> RazorpayEvidenceSyncService:
    """Dependency provider for RazorpayEvidenceSyncService."""
    is_placeholder = (
        not settings.RAZORPAY_KEY_ID
        or settings.RAZORPAY_KEY_ID.startswith("rzp_test_sample")
        or settings.RAZORPAY_KEY_SECRET == "samplesecretkey123456"
    )

    if settings.ENVIRONMENT in ("test", "testing") or "PYTEST_CURRENT_TEST" in os.environ or is_placeholder:
        client = MockRazorpayClient()
    else:
        client = HttpRazorpayClient(settings)

    razorpay_service = RazorpayService(client=client)
    return RazorpayEvidenceSyncService(razorpay_service=razorpay_service)


@router.post(
    "/{dispute_id}/sync",
    response_model=DisputeSyncResult,
    summary="Synchronize a dispute from Razorpay",
    description=(
        "Fetches the dispute from Razorpay's read-only API and synchronizes "
        "it with the local database. Financial identity fields (payment_id, "
        "amount, currency) are conflict-protected. This endpoint NEVER "
        "mutates Razorpay."
    ),
)
async def sync_dispute(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
    sync_service: RazorpayDisputeSyncService = Depends(_get_sync_service),
) -> DisputeSyncResult:
    """
    Synchronize a single dispute from Razorpay to local database.

    Returns a DisputeSyncResult with action, changed fields, and any conflicts.
    """
    return await sync_service.sync_dispute(dispute_id=dispute_id, db=db)


@router.post(
    "/{dispute_id}/sync-evidence",
    response_model=DisputeEvidenceSyncResult,
    summary="Synchronize dispute evidence documents from Razorpay",
    description=(
        "Fetches dispute evidence references from Razorpay, downloads document "
        "metadata and bounded binary content streams, and securely ingests "
        "them as local EvidenceDocument records. This endpoint NEVER mutates Razorpay."
    ),
)
async def sync_dispute_evidence(
    dispute_id: str,
    db: AsyncSession = Depends(get_db),
    sync_service: RazorpayEvidenceSyncService = Depends(_get_evidence_sync_service),
) -> DisputeEvidenceSyncResult:
    """
    Synchronize evidence documents for a dispute from Razorpay to local database.

    Returns a DisputeEvidenceSyncResult with status, counts, and per-document results.
    """
    return await sync_service.sync_dispute_evidence(dispute_id=dispute_id, db=db)
