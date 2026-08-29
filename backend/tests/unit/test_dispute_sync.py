"""
Test Suite: Razorpay → Local Dispute Synchronization (Task 3.2)

Tests the complete synchronization pipeline:
- New dispute creation from Razorpay
- Status/operational field updates
- Financial identity conflict detection
- Idempotency (sync twice = UNCHANGED)
- Webhook compatibility (webhook + sync coexist)
- Audit trail creation
- Razorpay error propagation
- Financial safety invariant (no Razorpay mutations)
- Credential safety

ALL tests use MockRazorpayClient. ZERO real API calls.
"""

import inspect
import json
import hmac
import hashlib
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.main import app
from backend.app.models.dispute import Dispute
from backend.app.models.sync_audit import DisputeSyncAudit
from backend.app.schemas.sync import DisputeSyncResult, SyncConflict
from backend.app.services.dispute_sync_service import (
    FINANCIAL_IDENTITY_FIELDS,
    OPERATIONAL_FIELDS,
    RazorpayDisputeSyncService,
)
from backend.app.services.razorpay_client import MockRazorpayClient, HttpRazorpayClient
from backend.app.services.razorpay_service import RazorpayService


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

VALID_RAZORPAY_DISPUTE = {
    "id": "disp_sync_test_001",
    "entity": "dispute",
    "payment_id": "pay_sync_test_001",
    "amount": 500000,
    "currency": "INR",
    "amount_deducted": 500000,
    "reason_code": "chargeback",
    "reason_description": "Product not delivered",
    "respond_by": 1770000000,
    "status": "open",
    "phase": "chargeback",
    "created_at": 1769000000,
}


def _make_mock_client(disputes=None, error_mode=None):
    """Create a MockRazorpayClient with optional custom disputes."""
    mock_disputes = {}
    if disputes:
        for d in disputes:
            mock_disputes[d["id"]] = d
    return MockRazorpayClient(mock_disputes=mock_disputes, error_mode=error_mode)


def _make_sync_service(client):
    """Create a RazorpayDisputeSyncService with a given client."""
    razorpay_service = RazorpayService(client=client)
    return RazorpayDisputeSyncService(razorpay_service=razorpay_service)


# ---------------------------------------------------------------------------
# Webhook helpers (reused from test_webhook_security.py patterns)
# ---------------------------------------------------------------------------

def _generate_signature(payload_bytes, secret=settings.RAZORPAY_WEBHOOK_SECRET):
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()


def _make_webhook_payload(dispute_id, amount=500000, status="open"):
    return {
        "entity": "event",
        "account_id": "acc_sync_test",
        "event": "payment.dispute.created",
        "contains": ["dispute"],
        "payload": {
            "dispute": {
                "entity": {
                    "id": dispute_id,
                    "entity": "dispute",
                    "payment_id": "pay_sync_test_001",
                    "amount": amount,
                    "currency": "INR",
                    "amount_deducted": amount,
                    "reason_code": "13.1",
                    "reason_description": "Merchandise/Services Not Received",
                    "status": status,
                    "phase": "chargeback",
                    "respond_by": 1770000000,
                }
            }
        },
        "created_at": 1769000000,
    }


# ===========================================================================
# 1. CORE SYNC SCENARIO TESTS
# ===========================================================================


class TestCoreSyncScenarios:
    """Test basic synchronization flows."""

    @pytest.mark.asyncio
    async def test_sync_new_dispute(self, async_db):
        """Syncing a dispute not in local DB creates it — returns CREATED."""
        client = _make_mock_client(disputes=[VALID_RAZORPAY_DISPUTE])
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_sync_test_001", async_db)
        await async_db.commit()

        assert result.action == "CREATED"
        assert result.dispute_id == "disp_sync_test_001"
        assert len(result.changed_fields) > 0
        assert len(result.conflicts) == 0

        # Verify local dispute was created
        stmt = select(Dispute).where(Dispute.id == "disp_sync_test_001")
        db_result = await async_db.execute(stmt)
        dispute = db_result.scalar_one_or_none()
        assert dispute is not None
        assert dispute.payment_id == "pay_sync_test_001"
        assert dispute.amount == 500000
        assert dispute.currency == "INR"
        assert dispute.status == "open"

    @pytest.mark.asyncio
    async def test_sync_existing_unchanged(self, async_db):
        """Syncing identical data returns UNCHANGED."""
        # Pre-create local dispute
        local = Dispute(
            id="disp_sync_test_001",
            entity="dispute",
            payment_id="pay_sync_test_001",
            amount=500000,
            currency="INR",
            amount_deducted=500000,
            reason_code="chargeback",
            reason_description="Product not delivered",
            status="open",
            phase="chargeback",
            respond_by=datetime.utcfromtimestamp(1770000000),
        )
        async_db.add(local)
        await async_db.flush()

        client = _make_mock_client(disputes=[VALID_RAZORPAY_DISPUTE])
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_sync_test_001", async_db)

        assert result.action == "UNCHANGED"
        assert len(result.changed_fields) == 0
        assert len(result.conflicts) == 0
        assert len(result.unchanged_fields) > 0

    @pytest.mark.asyncio
    async def test_sync_status_update(self, async_db):
        """Status change is safely updated — returns UPDATED."""
        local = Dispute(
            id="disp_sync_test_001",
            entity="dispute",
            payment_id="pay_sync_test_001",
            amount=500000,
            currency="INR",
            amount_deducted=500000,
            reason_code="chargeback",
            status="open",
            phase="chargeback",
            respond_by=datetime.utcfromtimestamp(1770000000),
        )
        async_db.add(local)
        await async_db.flush()

        # Razorpay now says status is "under_review"
        updated_dispute = {**VALID_RAZORPAY_DISPUTE, "status": "under_review"}
        client = _make_mock_client(disputes=[updated_dispute])
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_sync_test_001", async_db)

        assert result.action == "UPDATED"
        assert "status" in result.changed_fields
        assert len(result.conflicts) == 0

        # Verify local was updated
        await async_db.refresh(local)
        assert local.status == "under_review"

    @pytest.mark.asyncio
    async def test_sync_respond_by_update(self, async_db):
        """respond_by change is safely updated."""
        local = Dispute(
            id="disp_sync_test_001",
            entity="dispute",
            payment_id="pay_sync_test_001",
            amount=500000,
            currency="INR",
            amount_deducted=500000,
            reason_code="chargeback",
            status="open",
            phase="chargeback",
            respond_by=datetime.utcfromtimestamp(1770000000),
        )
        async_db.add(local)
        await async_db.flush()

        # Razorpay now has a different respond_by
        updated = {**VALID_RAZORPAY_DISPUTE, "respond_by": 1780000000}
        client = _make_mock_client(disputes=[updated])
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_sync_test_001", async_db)

        assert result.action == "UPDATED"
        assert "respond_by" in result.changed_fields

    @pytest.mark.asyncio
    async def test_sync_multiple_field_update(self, async_db):
        """Multiple operational field changes are all applied."""
        local = Dispute(
            id="disp_sync_test_001",
            entity="dispute",
            payment_id="pay_sync_test_001",
            amount=500000,
            currency="INR",
            amount_deducted=500000,
            reason_code="chargeback",
            status="open",
            phase="chargeback",
            respond_by=datetime.utcfromtimestamp(1770000000),
        )
        async_db.add(local)
        await async_db.flush()

        updated = {
            **VALID_RAZORPAY_DISPUTE,
            "status": "won",
            "phase": "arbitration",
            "reason_description": "Updated description",
        }
        client = _make_mock_client(disputes=[updated])
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_sync_test_001", async_db)

        assert result.action == "UPDATED"
        assert "status" in result.changed_fields
        assert "phase" in result.changed_fields
        assert "reason_description" in result.changed_fields


# ===========================================================================
# 2. CONFLICT DETECTION TESTS
# ===========================================================================


class TestConflictDetection:
    """Test financial identity conflict detection."""

    @pytest.mark.asyncio
    async def test_amount_conflict(self, async_db):
        """Amount differs → CONFLICT, local NOT overwritten."""
        local = Dispute(
            id="disp_sync_test_001",
            entity="dispute",
            payment_id="pay_sync_test_001",
            amount=500000,
            currency="INR",
            reason_code="chargeback",
            status="open",
        )
        async_db.add(local)
        await async_db.flush()

        # Razorpay says 600000 — different amount!
        conflict_dispute = {**VALID_RAZORPAY_DISPUTE, "amount": 600000}
        client = _make_mock_client(disputes=[conflict_dispute])
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_sync_test_001", async_db)

        assert result.action == "CONFLICT"
        assert len(result.conflicts) >= 1
        amount_conflict = next(c for c in result.conflicts if c.field == "amount")
        assert amount_conflict.local_value == 500000
        assert amount_conflict.razorpay_value == 600000
        assert "amount" in amount_conflict.reason.lower() or "Financial" in amount_conflict.reason

        # Verify local was NOT overwritten
        await async_db.refresh(local)
        assert local.amount == 500000

    @pytest.mark.asyncio
    async def test_payment_id_conflict(self, async_db):
        """payment_id differs → CONFLICT."""
        local = Dispute(
            id="disp_sync_test_001",
            entity="dispute",
            payment_id="pay_original_001",
            amount=500000,
            currency="INR",
            reason_code="chargeback",
            status="open",
        )
        async_db.add(local)
        await async_db.flush()

        # Razorpay reports different payment_id
        conflict_dispute = {**VALID_RAZORPAY_DISPUTE, "payment_id": "pay_sync_test_001"}
        client = _make_mock_client(disputes=[conflict_dispute])
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_sync_test_001", async_db)

        assert result.action == "CONFLICT"
        pid_conflict = next(c for c in result.conflicts if c.field == "payment_id")
        assert pid_conflict.local_value == "pay_original_001"
        assert pid_conflict.razorpay_value == "pay_sync_test_001"

    @pytest.mark.asyncio
    async def test_currency_conflict(self, async_db):
        """currency differs → CONFLICT."""
        local = Dispute(
            id="disp_sync_test_001",
            entity="dispute",
            payment_id="pay_sync_test_001",
            amount=500000,
            currency="USD",
            reason_code="chargeback",
            status="open",
        )
        async_db.add(local)
        await async_db.flush()

        client = _make_mock_client(disputes=[VALID_RAZORPAY_DISPUTE])
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_sync_test_001", async_db)

        assert result.action == "CONFLICT"
        cur_conflict = next(c for c in result.conflicts if c.field == "currency")
        assert cur_conflict.local_value == "USD"
        assert cur_conflict.razorpay_value == "INR"

    @pytest.mark.asyncio
    async def test_multiple_field_conflict(self, async_db):
        """Multiple financial identity fields differ → all reported."""
        local = Dispute(
            id="disp_sync_test_001",
            entity="dispute",
            payment_id="pay_different",
            amount=999999,
            currency="USD",
            reason_code="chargeback",
            status="open",
        )
        async_db.add(local)
        await async_db.flush()

        client = _make_mock_client(disputes=[VALID_RAZORPAY_DISPUTE])
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_sync_test_001", async_db)

        assert result.action == "CONFLICT"
        conflict_fields = {c.field for c in result.conflicts}
        assert "payment_id" in conflict_fields
        assert "amount" in conflict_fields
        assert "currency" in conflict_fields


# ===========================================================================
# 3. IDEMPOTENCY & CONCURRENCY TESTS
# ===========================================================================


class TestIdempotency:
    """Test synchronization idempotency."""

    @pytest.mark.asyncio
    async def test_sync_idempotency(self, async_db):
        """Sync twice with same data → CREATED then UNCHANGED."""
        client = _make_mock_client(disputes=[VALID_RAZORPAY_DISPUTE])
        service = _make_sync_service(client)

        result1 = await service.sync_dispute("disp_sync_test_001", async_db)
        await async_db.commit()
        assert result1.action == "CREATED"

        result2 = await service.sync_dispute("disp_sync_test_001", async_db)
        assert result2.action == "UNCHANGED"

    @pytest.mark.asyncio
    async def test_duplicate_sync_no_duplicate_dispute(self, async_db):
        """Syncing multiple times never creates duplicate local records."""
        client = _make_mock_client(disputes=[VALID_RAZORPAY_DISPUTE])
        service = _make_sync_service(client)

        await service.sync_dispute("disp_sync_test_001", async_db)
        await async_db.commit()
        await service.sync_dispute("disp_sync_test_001", async_db)
        await async_db.commit()
        await service.sync_dispute("disp_sync_test_001", async_db)
        await async_db.commit()

        # Count local disputes
        stmt = select(Dispute).where(Dispute.id == "disp_sync_test_001")
        result = await async_db.execute(stmt)
        disputes = result.scalars().all()
        assert len(disputes) == 1


# ===========================================================================
# 4. WEBHOOK COMPATIBILITY TEST
# ===========================================================================


class TestWebhookCompatibility:
    """Test that webhook and sync paths coexist without corruption."""

    @pytest.mark.asyncio
    async def test_webhook_compatibility(self, client, async_db):
        """Webhook creates dispute, then sync updates status without corruption."""
        # Step 1: Webhook creates dispute
        payload = _make_webhook_payload("disp_sync_test_001", amount=500000, status="open")
        payload_bytes = json.dumps(payload).encode("utf-8")
        sig = _generate_signature(payload_bytes)

        resp = await client.post(
            "/api/webhooks/razorpay",
            content=payload_bytes,
            headers={
                "content-type": "application/json",
                "x-razorpay-signature": sig,
                "x-razorpay-event-id": "evt_sync_compat_001",
            },
        )
        assert resp.status_code == 200

        # Verify dispute created by webhook
        stmt = select(Dispute).where(Dispute.id == "disp_sync_test_001")
        result = await async_db.execute(stmt)
        dispute = result.scalar_one_or_none()
        assert dispute is not None
        assert dispute.status == "open"
        assert dispute.amount == 500000

        # Step 2: Sync with updated status from Razorpay
        updated_razorpay = {**VALID_RAZORPAY_DISPUTE, "status": "under_review"}
        mock_client = _make_mock_client(disputes=[updated_razorpay])
        sync_service = _make_sync_service(mock_client)

        sync_result = await sync_service.sync_dispute("disp_sync_test_001", async_db)
        await async_db.commit()

        assert sync_result.action == "UPDATED"
        assert "status" in sync_result.changed_fields
        assert len(sync_result.conflicts) == 0

        # Verify local dispute updated but NOT corrupted
        await async_db.refresh(dispute)
        assert dispute.status == "under_review"
        assert dispute.amount == 500000  # Unchanged
        assert dispute.payment_id == "pay_sync_test_001"  # Unchanged


# ===========================================================================
# 5. ERROR HANDLING TESTS
# ===========================================================================


class TestErrorHandling:
    """Test Razorpay error propagation through sync service."""

    @pytest.mark.asyncio
    async def test_not_found(self, async_db):
        """Razorpay returns 404 → sync result NOT_FOUND."""
        client = _make_mock_client(error_mode="not_found")
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_nonexistent", async_db)

        assert result.action == "NOT_FOUND"
        assert result.dispute_id == "disp_nonexistent"

    @pytest.mark.asyncio
    async def test_razorpay_auth_error(self, async_db):
        """Razorpay 401 → HTTP 502."""
        from fastapi import HTTPException

        client = _make_mock_client(error_mode="auth_error")
        service = _make_sync_service(client)

        with pytest.raises(HTTPException) as exc_info:
            await service.sync_dispute("disp_test", async_db)
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_razorpay_rate_limit(self, async_db):
        """Razorpay 429 → HTTP 429."""
        from fastapi import HTTPException

        client = _make_mock_client(error_mode="rate_limit")
        service = _make_sync_service(client)

        with pytest.raises(HTTPException) as exc_info:
            await service.sync_dispute("disp_test", async_db)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_razorpay_server_error(self, async_db):
        """Razorpay 500 → HTTP 502."""
        from fastapi import HTTPException

        client = _make_mock_client(error_mode="server_error")
        service = _make_sync_service(client)

        with pytest.raises(HTTPException) as exc_info:
            await service.sync_dispute("disp_test", async_db)
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_razorpay_network_error(self, async_db):
        """Razorpay timeout → HTTP 502."""
        from fastapi import HTTPException

        client = _make_mock_client(error_mode="timeout")
        service = _make_sync_service(client)

        with pytest.raises(HTTPException) as exc_info:
            await service.sync_dispute("disp_test", async_db)
        assert exc_info.value.status_code == 502


# ===========================================================================
# 6. AUDIT TRAIL TESTS
# ===========================================================================


class TestAuditTrail:
    """Test synchronization audit trail."""

    @pytest.mark.asyncio
    async def test_audit_created_on_new_sync(self, async_db):
        """Audit record is created when a dispute is synced."""
        client = _make_mock_client(disputes=[VALID_RAZORPAY_DISPUTE])
        service = _make_sync_service(client)

        await service.sync_dispute("disp_sync_test_001", async_db)
        await async_db.commit()

        stmt = select(DisputeSyncAudit).where(
            DisputeSyncAudit.dispute_id == "disp_sync_test_001"
        )
        result = await async_db.execute(stmt)
        audits = result.scalars().all()
        assert len(audits) >= 1
        assert audits[0].action == "CREATED"
        assert audits[0].source == "api_sync"

    @pytest.mark.asyncio
    async def test_audit_records_conflict(self, async_db):
        """Audit record captures conflict details."""
        local = Dispute(
            id="disp_sync_test_001",
            entity="dispute",
            payment_id="pay_sync_test_001",
            amount=999999,  # Different!
            currency="INR",
            reason_code="chargeback",
            status="open",
        )
        async_db.add(local)
        await async_db.flush()

        client = _make_mock_client(disputes=[VALID_RAZORPAY_DISPUTE])
        service = _make_sync_service(client)

        await service.sync_dispute("disp_sync_test_001", async_db)
        await async_db.commit()

        stmt = select(DisputeSyncAudit).where(
            DisputeSyncAudit.dispute_id == "disp_sync_test_001"
        )
        result = await async_db.execute(stmt)
        audit = result.scalars().first()
        assert audit is not None
        assert audit.action == "CONFLICT"
        assert audit.conflicts is not None
        assert len(audit.conflicts) >= 1

    @pytest.mark.asyncio
    async def test_raw_payload_no_credentials(self, async_db):
        """Stored raw_payload must not contain credentials."""
        client = _make_mock_client(disputes=[VALID_RAZORPAY_DISPUTE])
        service = _make_sync_service(client)

        await service.sync_dispute("disp_sync_test_001", async_db)
        await async_db.commit()

        stmt = select(Dispute).where(Dispute.id == "disp_sync_test_001")
        result = await async_db.execute(stmt)
        dispute = result.scalar_one()

        payload_str = json.dumps(dispute.raw_payload).lower()
        assert "key_id" not in payload_str
        assert "key_secret" not in payload_str
        assert "rzp_test" not in payload_str
        assert "authorization" not in payload_str

    @pytest.mark.asyncio
    async def test_sync_result_schema(self, async_db):
        """DisputeSyncResult has all expected fields."""
        client = _make_mock_client(disputes=[VALID_RAZORPAY_DISPUTE])
        service = _make_sync_service(client)

        result = await service.sync_dispute("disp_sync_test_001", async_db)

        assert isinstance(result, DisputeSyncResult)
        assert result.dispute_id is not None
        assert result.action in ("CREATED", "UPDATED", "UNCHANGED", "CONFLICT", "NOT_FOUND")
        assert isinstance(result.changed_fields, list)
        assert isinstance(result.unchanged_fields, list)
        assert isinstance(result.conflicts, list)
        assert isinstance(result.synchronized_at, datetime)


# ===========================================================================
# 7. FINANCIAL SAFETY INVARIANT TESTS
# ===========================================================================


class TestFinancialSafety:
    """Re-assert that the Razorpay client remains read-only."""

    FORBIDDEN_PREFIXES = (
        "accept_", "contest_", "submit_", "create_",
        "update_", "delete_", "patch_", "post_", "put_",
    )

    def _get_public_methods(self, cls):
        return [
            name for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
            if not name.startswith("_")
        ]

    def test_no_razorpay_mutation(self):
        """HttpRazorpayClient still has no mutation methods after Task 3.2."""
        methods = self._get_public_methods(HttpRazorpayClient)
        for method in methods:
            for prefix in self.FORBIDDEN_PREFIXES:
                assert not method.startswith(prefix), (
                    f"HttpRazorpayClient has forbidden mutation method: {method}"
                )

    def test_sync_endpoint_is_local_only(self):
        """The sync endpoint router has only POST (local mutation), no Razorpay mutation routes."""
        from backend.app.api.dispute_sync import router

        for route in router.routes:
            if hasattr(route, "methods"):
                # POST is allowed (it modifies LOCAL DB only)
                allowed = {"POST", "HEAD", "OPTIONS"}
                dangerous = route.methods - allowed
                assert not dangerous, (
                    f"Route {route.path} has unexpected methods: {dangerous}"
                )


# ===========================================================================
# 8. API ENDPOINT TESTS
# ===========================================================================


class TestSyncApiEndpoint:
    """Test the POST /api/disputes/{dispute_id}/sync endpoint."""

    @pytest.mark.asyncio
    async def test_sync_endpoint_creates_dispute(self, client, async_db):
        """POST /api/disputes/{id}/sync creates local dispute."""
        response = await client.post("/api/disputes/disp_mock_0/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "CREATED"
        assert data["dispute_id"] == "disp_mock_0"

    @pytest.mark.asyncio
    async def test_sync_endpoint_returns_sync_result(self, client, async_db):
        """Sync endpoint returns properly structured DisputeSyncResult."""
        response = await client.post("/api/disputes/disp_mock_0/sync")
        assert response.status_code == 200
        data = response.json()
        assert "dispute_id" in data
        assert "action" in data
        assert "changed_fields" in data
        assert "unchanged_fields" in data
        assert "conflicts" in data
        assert "synchronized_at" in data
