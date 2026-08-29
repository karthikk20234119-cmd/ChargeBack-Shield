"""
Razorpay → Local Dispute Synchronization Service — Task 3.2

Synchronizes a Razorpay dispute (fetched via read-only API client)
with the local Dispute model.

FINANCIAL SAFETY:
- Razorpay client remains READ ONLY
- This service mutates ONLY the local database
- Financial identity fields (payment_id, amount, currency) are
  CONFLICT-protected — never silently overwritten
- Operational fields (status, phase, respond_by, etc.) are
  Razorpay-authoritative and may be refreshed

SOURCE-OF-TRUTH POLICY:
┌─────────────────────────────────────────────────────────┐
│ Financial Identity Fields → CONFLICT if differs         │
│   payment_id, amount, currency                          │
│                                                         │
│ Operational Fields → Razorpay authoritative (refreshed) │
│   status, phase, respond_by, amount_deducted,           │
│   reason_code, reason_description                       │
│                                                         │
│ Webhook-Only Fields → Untouched during sync             │
│   customer_email, customer_contact                      │
└─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.dispute import Dispute
from backend.app.models.sync_audit import DisputeSyncAudit
from backend.app.schemas.razorpay import RazorpayDisputeResponse
from backend.app.schemas.sync import DisputeSyncResult, SyncConflict
from backend.app.services.razorpay_errors import (
    RazorpayClientError,
    RazorpayNotFoundError,
)
from backend.app.services.razorpay_service import RazorpayService

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Field Classification
# -------------------------------------------------------------------------

# Financial identity fields — CONFLICT if local != Razorpay
FINANCIAL_IDENTITY_FIELDS = {"payment_id", "amount", "currency"}

# Operational fields — Razorpay is authoritative, safe to refresh
OPERATIONAL_FIELDS = {
    "status",
    "phase",
    "respond_by",
    "amount_deducted",
    "reason_code",
    "reason_description",
}


class RazorpayDisputeSyncService:
    """
    Synchronizes Razorpay disputes with the local database.

    Uses explicit field mapping with conflict detection for
    financial identity fields. Records audit trail for every
    synchronization attempt.
    """

    def __init__(self, razorpay_service: RazorpayService):
        self._razorpay = razorpay_service

    async def sync_dispute(
        self, dispute_id: str, db: AsyncSession
    ) -> DisputeSyncResult:
        """
        Synchronize a single dispute from Razorpay to the local database.

        Flow:
        1. Validate dispute_id
        2. Fetch from Razorpay via read-only API
        3. Find local dispute
        4. Compare fields with explicit mapping
        5. Detect conflicts on financial identity fields
        6. Apply safe updates on operational fields
        7. Record audit trail
        8. Return typed DisputeSyncResult
        """
        if not dispute_id or not dispute_id.strip():
            raise HTTPException(status_code=400, detail="dispute_id is required")

        # Step 1: Fetch from Razorpay
        razorpay_dispute = await self._fetch_from_razorpay(dispute_id)
        if razorpay_dispute is None:
            return DisputeSyncResult(
                dispute_id=dispute_id,
                action="NOT_FOUND",
                changed_fields=[],
                unchanged_fields=[],
                conflicts=[],
                synchronized_at=datetime.utcnow(),
            )

        # Step 2: Find local dispute
        local_dispute = await self._find_local_dispute(dispute_id, db)

        # Step 3: Create or sync
        if local_dispute is None:
            return await self._create_from_razorpay(razorpay_dispute, db)
        else:
            return await self._sync_existing(local_dispute, razorpay_dispute, db)

    # ------------------------------------------------------------------
    # Internal: Razorpay fetch
    # ------------------------------------------------------------------

    async def _fetch_from_razorpay(
        self, dispute_id: str
    ) -> RazorpayDisputeResponse | None:
        """
        Fetch dispute from Razorpay. Returns None if not found.
        Re-raises all other errors as HTTPException.
        """
        try:
            return await self._razorpay.get_dispute(dispute_id)
        except HTTPException as exc:
            if exc.status_code == 404:
                return None
            raise

    # ------------------------------------------------------------------
    # Internal: Local dispute lookup
    # ------------------------------------------------------------------

    async def _find_local_dispute(
        self, dispute_id: str, db: AsyncSession
    ) -> Dispute | None:
        """Find existing local dispute by Razorpay ID."""
        stmt = select(Dispute).where(Dispute.id == dispute_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Internal: Create new local dispute from Razorpay data
    # ------------------------------------------------------------------

    async def _create_from_razorpay(
        self, razorpay: RazorpayDisputeResponse, db: AsyncSession
    ) -> DisputeSyncResult:
        """
        Create a new local dispute from Razorpay data.

        Handles concurrent creation via IntegrityError on PK conflict.
        """
        now = datetime.utcnow()
        respond_by_dt = self._convert_respond_by(razorpay.respond_by)

        new_dispute = Dispute(
            id=razorpay.id,
            entity=razorpay.entity,
            payment_id=razorpay.payment_id,
            amount=razorpay.amount,
            currency=razorpay.currency,
            amount_deducted=razorpay.amount_deducted,
            reason_code=razorpay.reason_code,
            reason_description=razorpay.reason_description,
            status=razorpay.status,
            phase=razorpay.phase,
            respond_by=respond_by_dt,
            raw_payload=razorpay.model_dump(),
        )

        try:
            db.add(new_dispute)
            await db.flush()
        except IntegrityError:
            # Concurrent creation — another process/request created it first
            await db.rollback()
            logger.info(
                "Concurrent dispute creation detected for %s, falling through to update",
                razorpay.id,
            )
            # Re-fetch the existing dispute and sync
            local_dispute = await self._find_local_dispute(razorpay.id, db)
            if local_dispute is not None:
                return await self._sync_existing(local_dispute, razorpay, db)
            # Should not happen, but safety fallback
            raise HTTPException(
                status_code=500,
                detail="Concurrent synchronization conflict could not be resolved",
            )

        # Record audit
        await self._record_audit(
            dispute_id=razorpay.id,
            action="CREATED",
            changed_fields=list(FINANCIAL_IDENTITY_FIELDS | OPERATIONAL_FIELDS),
            conflicts=[],
            razorpay_data=razorpay.model_dump(),
            db=db,
        )

        await db.flush()

        logger.info("Created local dispute from Razorpay sync: %s", razorpay.id)

        return DisputeSyncResult(
            dispute_id=razorpay.id,
            action="CREATED",
            changed_fields=list(FINANCIAL_IDENTITY_FIELDS | OPERATIONAL_FIELDS),
            unchanged_fields=[],
            conflicts=[],
            synchronized_at=now,
        )

    # ------------------------------------------------------------------
    # Internal: Sync existing local dispute
    # ------------------------------------------------------------------

    async def _sync_existing(
        self,
        local: Dispute,
        razorpay: RazorpayDisputeResponse,
        db: AsyncSession,
    ) -> DisputeSyncResult:
        """
        Synchronize an existing local dispute with Razorpay data.

        1. Check financial identity fields for conflicts
        2. If conflicts exist → return CONFLICT (no update)
        3. Compare operational fields → apply safe updates
        4. Record audit trail
        """
        now = datetime.utcnow()

        # Step 1: Check financial identity fields
        conflicts = self._detect_conflicts(local, razorpay)

        if conflicts:
            # Record audit with conflicts
            await self._record_audit(
                dispute_id=razorpay.id,
                action="CONFLICT",
                changed_fields=[],
                conflicts=[c.model_dump() for c in conflicts],
                razorpay_data=razorpay.model_dump(),
                db=db,
            )
            await db.flush()

            logger.warning(
                "Sync conflict for dispute %s: %d field(s) differ",
                razorpay.id,
                len(conflicts),
            )

            return DisputeSyncResult(
                dispute_id=razorpay.id,
                action="CONFLICT",
                changed_fields=[],
                unchanged_fields=[],
                conflicts=conflicts,
                synchronized_at=now,
            )

        # Step 2: Compare operational fields
        changed_fields: list[str] = []
        unchanged_fields: list[str] = []

        for field_name in sorted(OPERATIONAL_FIELDS):
            new_value = self._get_razorpay_field_value(razorpay, field_name)
            local_value = self._get_local_field_value(local, field_name)

            if local_value != new_value:
                setattr(local, field_name, new_value)
                changed_fields.append(field_name)
            else:
                unchanged_fields.append(field_name)

        # Financial identity fields are unchanged (no conflicts detected above)
        for field_name in sorted(FINANCIAL_IDENTITY_FIELDS):
            unchanged_fields.append(field_name)

        # Update raw_payload with sanitized Razorpay data
        local.raw_payload = razorpay.model_dump()

        # Step 3: Determine action
        if changed_fields:
            action = "UPDATED"
        else:
            action = "UNCHANGED"

        # Record audit
        await self._record_audit(
            dispute_id=razorpay.id,
            action=action,
            changed_fields=changed_fields,
            conflicts=[],
            razorpay_data=razorpay.model_dump(),
            db=db,
        )

        await db.flush()

        if changed_fields:
            logger.info(
                "Updated dispute %s: %s",
                razorpay.id,
                ", ".join(changed_fields),
            )
        else:
            logger.info("Dispute %s unchanged after sync", razorpay.id)

        return DisputeSyncResult(
            dispute_id=razorpay.id,
            action=action,
            changed_fields=changed_fields,
            unchanged_fields=unchanged_fields,
            conflicts=[],
            synchronized_at=now,
        )

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def _detect_conflicts(
        self, local: Dispute, razorpay: RazorpayDisputeResponse
    ) -> list[SyncConflict]:
        """
        Compare financial identity fields between local and Razorpay.

        Returns a list of SyncConflict for each field that differs.
        """
        conflicts: list[SyncConflict] = []

        field_checks = [
            ("payment_id", local.payment_id, razorpay.payment_id, "Payment ID differs"),
            ("amount", local.amount, razorpay.amount, "Financial amount differs"),
            ("currency", local.currency, razorpay.currency, "Currency differs"),
        ]

        for field_name, local_val, razorpay_val, reason in field_checks:
            if local_val != razorpay_val:
                conflicts.append(
                    SyncConflict(
                        field=field_name,
                        local_value=local_val,
                        razorpay_value=razorpay_val,
                        reason=reason,
                    )
                )

        return conflicts

    # ------------------------------------------------------------------
    # Field value extraction (explicit mapping, no dict unpacking)
    # ------------------------------------------------------------------

    def _get_razorpay_field_value(
        self, razorpay: RazorpayDisputeResponse, field_name: str
    ) -> Any:
        """
        Get the mapped value from RazorpayDisputeResponse for a local field.

        Explicit mapping — no implicit dict unpacking.
        """
        if field_name == "respond_by":
            return self._convert_respond_by(razorpay.respond_by)

        # Direct 1:1 mapping for all other operational fields
        return getattr(razorpay, field_name)

    def _get_local_field_value(self, local: Dispute, field_name: str) -> Any:
        """Get current value from local Dispute model."""
        return getattr(local, field_name)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_respond_by(unix_timestamp: int | None) -> datetime | None:
        """
        Convert Razorpay Unix timestamp to datetime.

        Returns None if timestamp is None or invalid.
        Does not change timezone semantics (stores as UTC).
        """
        if unix_timestamp is None:
            return None
        try:
            return datetime.utcfromtimestamp(unix_timestamp)
        except (ValueError, OSError, OverflowError):
            logger.warning("Invalid respond_by timestamp: %s", unix_timestamp)
            return None

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------

    async def _record_audit(
        self,
        dispute_id: str,
        action: str,
        changed_fields: list[str],
        conflicts: list[dict],
        razorpay_data: dict,
        db: AsyncSession,
    ) -> None:
        """
        Record a synchronization audit entry.

        The razorpay_data is already sanitized (from model_dump() which
        excludes evidence per Task 3.1 schema). No credentials stored.
        """
        audit = DisputeSyncAudit(
            dispute_id=dispute_id,
            source="api_sync",
            action=action,
            changed_fields=changed_fields,
            conflicts=conflicts if conflicts else None,
            raw_razorpay_data=razorpay_data,
        )
        db.add(audit)
