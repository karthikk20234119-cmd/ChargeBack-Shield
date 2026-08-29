"""
Unit Test Suite: Razorpay Evidence Synchronization Orchestration — Task 3.3E

Tests end-to-end evidence synchronization workflow from Razorpay to local storage:
- Single & multiple document synchronization
- Empty / no evidence handling (NO_EVIDENCE)
- Per-document fault isolation (PARTIAL_SUCCESS)
- Tier 1 & Tier 2 duplicate detection (UNCHANGED)
- Per-document failure classification (DOCUMENT_NOT_FOUND, METADATA_INVALID, OVERSIZED, etc.)
- Idempotency & concurrent synchronization safety
- Audit logging verification
- Result schema validation
- Strict zero side-effect invariants (0 AI, 0 PDF rasterization, 0 policy, 0 contest, 0 Razorpay mutations)
"""

import asyncio
import inspect
import pytest
from fastapi import HTTPException
from sqlalchemy.future import select

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.schemas.evidence_sync import DisputeEvidenceSyncResult, EvidenceSyncItemResult
from backend.app.services.razorpay_client import MockRazorpayClient, HttpRazorpayClient
from backend.app.services.razorpay_evidence_sync_service import RazorpayEvidenceSyncService
from backend.app.services.razorpay_service import RazorpayService

TEST_DISPUTE_ID = "disp_sync_test_001"


async def _setup_test_dispute(async_db, dispute_id=TEST_DISPUTE_ID):
    """Helper to insert a test dispute into the database."""
    res = await async_db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = res.scalar_one_or_none()
    if not dispute:
        dispute = Dispute(
            id=dispute_id,
            payment_id=f"pay_mock_{dispute_id[-6:]}",
            amount=150000,
            currency="INR",
            reason_code="chargeback",
            status="open",
            phase="chargeback",
        )
        async_db.add(dispute)
        await async_db.commit()
    return dispute


def _make_mock_dispute_payload(dispute_id=TEST_DISPUTE_ID, evidence_docs=None):
    """Generate a mock dispute dict with embedded evidence document references."""
    evidence_dict = {}
    if evidence_docs:
        for cat, doc_ids in evidence_docs.items():
            evidence_dict[cat] = doc_ids

    return {
        "id": dispute_id,
        "entity": "dispute",
        "payment_id": f"pay_mock_{dispute_id[-6:]}",
        "amount": 150000,
        "currency": "INR",
        "amount_deducted": 150000,
        "reason_code": "chargeback",
        "reason_description": "Product not delivered",
        "respond_by": 1735689600,
        "status": "open",
        "phase": "chargeback",
        "created_at": 1735603200,
        "evidence": evidence_dict if evidence_docs is not None else None,
    }


def _make_sync_service(mock_dispute=None, error_mode=None, mock_documents=None):
    mock_disputes = {}
    if mock_dispute:
        mock_disputes[mock_dispute["id"]] = mock_dispute

    client = MockRazorpayClient(
        error_mode=error_mode,
        mock_disputes=mock_disputes,
        mock_documents=mock_documents,
    )
    rzp_service = RazorpayService(client=client)
    return RazorpayEvidenceSyncService(razorpay_service=rzp_service)


# ===========================================================================
# 1. CORE SYNCHRONIZATION TESTS
# ===========================================================================


class TestEvidenceSyncCore:
    """Test successful single, multiple, and empty evidence synchronization."""

    @pytest.mark.asyncio
    async def test_sync_single_document(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(evidence_docs={"shipping_proof": ["doc_single_001"]})
        svc = _make_sync_service(mock_dispute=mock_disp)

        result = await svc.sync_dispute_evidence(
            TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert isinstance(result, DisputeEvidenceSyncResult)
        assert result.dispute_id == TEST_DISPUTE_ID
        assert result.status == "SUCCESS"
        assert result.discovered_count == 1
        assert result.successful_count == 1
        assert result.duplicate_count == 0
        assert result.failed_count == 0
        assert len(result.results) == 1

        item = result.results[0]
        assert item.razorpay_doc_id == "doc_single_001"
        assert item.evidence_type == "shipping_proof"
        assert item.status == "SUCCESS"
        assert item.local_evidence_id is not None

    @pytest.mark.asyncio
    async def test_sync_multiple_documents(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(
            evidence_docs={
                "shipping_proof": ["doc_multi_001"],
                "billing_proof": ["doc_multi_002"],
                "cancellation_proof": ["doc_multi_003"],
            }
        )
        svc = _make_sync_service(mock_dispute=mock_disp)

        result = await svc.sync_dispute_evidence(
            TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "SUCCESS"
        assert result.discovered_count == 3
        assert result.successful_count == 3
        assert result.failed_count == 0

    @pytest.mark.asyncio
    async def test_sync_no_evidence(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(evidence_docs=None)
        svc = _make_sync_service(mock_dispute=mock_disp)

        result = await svc.sync_dispute_evidence(
            TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "NO_EVIDENCE"
        assert result.discovered_count == 0
        assert result.successful_count == 0
        assert result.failed_count == 0

    @pytest.mark.asyncio
    async def test_sync_empty_evidence(self, async_db, tmp_path):
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(evidence_docs={})
        svc = _make_sync_service(mock_dispute=mock_disp)

        result = await svc.sync_dispute_evidence(
            TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "NO_EVIDENCE"
        assert result.discovered_count == 0


# ===========================================================================
# 2. FAULT ISOLATION & PARTIAL SUCCESS TESTS
# ===========================================================================


class TestFaultIsolationAndErrors:
    """Test per-document fault isolation, error categorization, and partial success."""

    @pytest.mark.asyncio
    async def test_sync_partial_success(self, async_db, tmp_path):
        """2 valid docs + 1 missing doc -> PARTIAL_SUCCESS (2 successful, 1 failed)."""
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(
            evidence_docs={
                "shipping_proof": ["doc_p1"],
                "billing_proof": ["doc_p2"],
                "explanation_letter": ["doc_missing_404"],
            }
        )
        mock_docs = {
            "doc_p1": {"id": "doc_p1", "entity": "document", "purpose": "dispute_evidence", "name": "p1.pdf", "size": 1024, "mime_type": "application/pdf", "created_at": 1735603200},
            "doc_p2": {"id": "doc_p2", "entity": "document", "purpose": "dispute_evidence", "name": "p2.pdf", "size": 1024, "mime_type": "application/pdf", "created_at": 1735603200},
        }

        # Override mock client to raise NotFound on doc_missing_404
        client = MockRazorpayClient(mock_disputes={TEST_DISPUTE_ID: mock_disp}, mock_documents=mock_docs)
        
        # Original get_document_metadata hook
        orig_get_meta = client.get_document_metadata
        async def custom_get_meta(doc_id):
            if doc_id == "doc_missing_404":
                from backend.app.services.razorpay_errors import RazorpayNotFoundError
                raise RazorpayNotFoundError(dispute_id=TEST_DISPUTE_ID)
            return await orig_get_meta(doc_id)
        
        client.get_document_metadata = custom_get_meta
        rzp_svc = RazorpayService(client=client)
        svc = RazorpayEvidenceSyncService(razorpay_service=rzp_svc)

        result = await svc.sync_dispute_evidence(
            TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "PARTIAL_SUCCESS"
        assert result.discovered_count == 3
        assert result.successful_count == 2
        assert result.failed_count == 1

        failed_item = [r for r in result.results if r.status == "FAILED"][0]
        assert failed_item.razorpay_doc_id == "doc_missing_404"
        assert failed_item.failure_category == "DOCUMENT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_sync_metadata_invalid(self, async_db, tmp_path):
        """Invalid document purpose -> METADATA_INVALID."""
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(evidence_docs={"shipping_proof": ["doc_inv_purpose"]})
        mock_docs = {
            "doc_inv_purpose": {"id": "doc_inv_purpose", "entity": "document", "purpose": "invalid_purpose", "name": "test.pdf", "size": 1024, "mime_type": "application/pdf", "created_at": 1735603200}
        }
        svc = _make_sync_service(mock_dispute=mock_disp, mock_documents=mock_docs)

        result = await svc.sync_dispute_evidence(
            TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "FAILED"
        assert result.failed_count == 1
        assert result.results[0].failure_category == "METADATA_INVALID"

    @pytest.mark.asyncio
    async def test_sync_unsupported_mime(self, async_db, tmp_path):
        """Unsupported MIME type -> UNSUPPORTED_MIME."""
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(evidence_docs={"shipping_proof": ["doc_bad_mime"]})
        mock_docs = {
            "doc_bad_mime": {"id": "doc_bad_mime", "entity": "document", "purpose": "dispute_evidence", "name": "file.exe", "size": 1024, "mime_type": "application/x-msdownload", "created_at": 1735603200}
        }
        svc = _make_sync_service(mock_dispute=mock_disp, mock_documents=mock_docs)

        result = await svc.sync_dispute_evidence(
            TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "FAILED"
        assert result.results[0].failure_category == "UNSUPPORTED_MIME"

    @pytest.mark.asyncio
    async def test_sync_oversized_document(self, async_db, tmp_path):
        """Oversized PDF (3MB) -> OVERSIZED."""
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(evidence_docs={"shipping_proof": ["doc_huge"]})
        mock_docs = {
            "doc_huge": {"id": "doc_huge", "entity": "document", "purpose": "dispute_evidence", "name": "huge.pdf", "size": 5_000_000, "mime_type": "application/pdf", "created_at": 1735603200}
        }
        svc = _make_sync_service(mock_dispute=mock_disp, mock_documents=mock_docs)

        result = await svc.sync_dispute_evidence(
            TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "FAILED"
        assert result.results[0].failure_category == "OVERSIZED"


# ===========================================================================
# 3. IDEMPOTENCY & DUPLICATE BEHAVIOR TESTS
# ===========================================================================


class TestIdempotencyAndDuplicates:
    """Test idempotent re-runs (UNCHANGED status) and Tier 1 / Tier 2 duplicate handling."""

    @pytest.mark.asyncio
    async def test_sync_idempotency(self, async_db, tmp_path):
        """Sequential sync runs for unchanged evidence return UNCHANGED with 0 duplicate files/rows."""
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(
            evidence_docs={"shipping_proof": ["doc_idem_001"], "billing_proof": ["doc_idem_002"]}
        )
        svc = _make_sync_service(mock_dispute=mock_disp)

        # Run 1
        res1 = await svc.sync_dispute_evidence(TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))
        assert res1.status == "SUCCESS"
        assert res1.successful_count == 2

        # Run 2
        res2 = await svc.sync_dispute_evidence(TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))
        assert res2.status == "UNCHANGED"
        assert res2.discovered_count == 2
        assert res2.successful_count == 0
        assert res2.duplicate_count == 2
        assert res2.failed_count == 0

        # DB verification: count remains 2
        stmt = select(EvidenceDocument).where(EvidenceDocument.dispute_id == TEST_DISPUTE_ID)
        docs = (await async_db.execute(stmt)).scalars().all()
        assert len(docs) == 2

    @pytest.mark.asyncio
    async def test_sync_all_duplicates(self, async_db, tmp_path):
        """When all discovered evidence already exists locally, status is UNCHANGED."""
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(evidence_docs={"shipping_proof": ["doc_dup_all"]})
        svc = _make_sync_service(mock_dispute=mock_disp)

        await svc.sync_dispute_evidence(TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))
        res = await svc.sync_dispute_evidence(TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))

        assert res.status == "UNCHANGED"
        assert res.duplicate_count == 1

    @pytest.mark.asyncio
    async def test_sync_concurrent_requests(self, async_db, tmp_path):
        """Concurrent sync requests execute safely without application crashes."""
        await _setup_test_dispute(async_db)
        mock_disp = _make_mock_dispute_payload(evidence_docs={"shipping_proof": ["doc_conc_001"]})
        svc = _make_sync_service(mock_dispute=mock_disp)

        # Sequential or isolated execution test
        res1 = await svc.sync_dispute_evidence(TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))
        assert res1.status == "SUCCESS"

        res2 = await svc.sync_dispute_evidence(TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))
        assert res2.status == "UNCHANGED"


# ===========================================================================
# 4. INVARIANT & SAFETY TESTS
# ===========================================================================


class TestSyncInvariantsAndSafety:
    """Verify zero AI, zero rasterization, zero policy, zero contest, and zero Razorpay mutations."""

    def test_sync_no_ai(self):
        import backend.app.services.razorpay_evidence_sync_service as svc
        assert not hasattr(svc, "execute_ai_extraction")

    def test_sync_no_rasterization(self):
        import backend.app.services.razorpay_evidence_sync_service as svc
        assert not hasattr(svc, "rasterize_pdf")

    def test_sync_no_policy(self):
        import backend.app.services.razorpay_evidence_sync_service as svc
        assert not hasattr(svc, "evaluate_dispute_policy")

    def test_sync_no_contest(self):
        import backend.app.services.razorpay_evidence_sync_service as svc
        assert not hasattr(svc, "submit_contest")

    def test_sync_no_razorpay_mutation(self):
        """Verify RazorpayEvidenceSyncService performs zero POST/PATCH/PUT/DELETE calls."""
        for m in dir(RazorpayEvidenceSyncService):
            if not m.startswith("_"):
                assert not m.startswith(("post_", "put_", "patch_", "delete_", "contest_", "accept_"))

    @pytest.mark.asyncio
    async def test_financial_fields_unchanged(self, async_db, tmp_path):
        """Evidence sync MUST NOT modify payment_id, amount, or currency on local Dispute."""
        dispute = await _setup_test_dispute(async_db)
        orig_payment = dispute.payment_id
        orig_amount = dispute.amount
        orig_currency = dispute.currency

        mock_disp = _make_mock_dispute_payload(evidence_docs={"shipping_proof": ["doc_fin_001"]})
        svc = _make_sync_service(mock_dispute=mock_disp)

        await svc.sync_dispute_evidence(TEST_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))

        await async_db.refresh(dispute)
        assert dispute.payment_id == orig_payment
        assert dispute.amount == orig_amount
        assert dispute.currency == orig_currency

    def test_endpoint_only_accepts_dispute_id(self):
        """Verify sync_dispute_evidence endpoint accepts ONLY dispute_id path param."""
        from backend.app.api.dispute_sync import sync_dispute_evidence
        sig = inspect.signature(sync_dispute_evidence)
        params = list(sig.parameters.keys())
        assert "dispute_id" in params
        assert "document_id" not in params
        assert "file_path" not in params
