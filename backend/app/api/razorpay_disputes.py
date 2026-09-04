"""
Razorpay Disputes — Read-Only API Router

Exposes GET endpoints for fetching dispute data from the Razorpay API.

FINANCIAL SAFETY: This router contains ONLY GET endpoints.
No POST, PATCH, PUT, or DELETE endpoints exist.
No mutation operations. No credentials in responses.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.app.config import settings
from backend.app.schemas.razorpay import (
    RazorpayDisputeListResponse,
    RazorpayDisputeResponse,
    RazorpayDocumentMetadataResponse,
)
from backend.app.services.razorpay_client import MockRazorpayClient, HttpRazorpayClient
from backend.app.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/razorpay", tags=["razorpay-disputes"])


def _get_razorpay_service() -> RazorpayService:
    """
    Dependency provider for RazorpayService.

    Uses MockRazorpayClient in test/development when Razorpay credentials
    are placeholder values; HttpRazorpayClient otherwise.
    """
    # Detect placeholder/test credentials
    is_placeholder = (
        not settings.RAZORPAY_KEY_ID
        or settings.RAZORPAY_KEY_ID.startswith("rzp_test_sample")
        or settings.RAZORPAY_KEY_SECRET == "samplesecretkey123456"
    )

    if settings.ENVIRONMENT == "test" or is_placeholder:
        client = MockRazorpayClient()
    else:
        client = HttpRazorpayClient(settings)

    return RazorpayService(client=client)


@router.get(
    "/disputes/{dispute_id}",
    response_model=RazorpayDisputeResponse,
    summary="Fetch a single Razorpay dispute",
    description="Retrieves dispute details from the Razorpay API by dispute ID. Read-only operation.",
)
async def get_dispute(
    dispute_id: str,
    service: RazorpayService = Depends(_get_razorpay_service),
) -> RazorpayDisputeResponse:
    """Fetch a single dispute from Razorpay API."""
    return await service.get_dispute(dispute_id)


@router.get(
    "/disputes",
    response_model=RazorpayDisputeListResponse,
    summary="List Razorpay disputes",
    description="Lists disputes from the Razorpay API with pagination. Read-only operation.",
)
async def list_disputes(
    skip: int = Query(default=0, ge=0, description="Number of disputes to skip"),
    count: int = Query(
        default=50, ge=1, le=100, description="Number of disputes per page (max 100)"
    ),
    service: RazorpayService = Depends(_get_razorpay_service),
) -> RazorpayDisputeListResponse:
    """List disputes from Razorpay API with pagination."""
    return await service.list_disputes(skip=skip, count=count)


@router.get(
    "/documents/{document_id}",
    response_model=RazorpayDocumentMetadataResponse,
    summary="Fetch Razorpay document metadata",
    description=(
        "Retrieves document metadata from the Razorpay API by document ID. "
        "Read-only operation. Does NOT download binary file content."
    ),
)
async def get_document_metadata(
    document_id: str,
    service: RazorpayService = Depends(_get_razorpay_service),
) -> RazorpayDocumentMetadataResponse:
    """
    Fetch Razorpay document metadata by document ID.

    Performs read-only metadata retrieval and pre-flight validation.
    Does NOT download file content or perform local file storage.
    """
    return await service.get_document_metadata(document_id)

