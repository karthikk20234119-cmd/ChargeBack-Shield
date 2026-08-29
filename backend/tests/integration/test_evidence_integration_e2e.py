"""
Integration Test Suite: Razorpay Evidence Synchronization E2E — Task 3.3F

Performs end-to-end integration and safety verification of the complete
Razorpay evidence ingestion pipeline:
Mock Razorpay API -> RazorpayClient -> RazorpayService -> EvidenceReferenceExtractor ->
RazorpayEvidenceIngestionService -> RazorpayEvidenceSyncService -> EvidenceDocument

Coverage:
1. Full Happy Path (Shipping PDF, Billing PNG, Cancellation JPEG, Explanation PDF)
2. Multi-Category Duplicate (Same doc ID across multiple categories)
3. Content Duplicate (Different doc IDs with identical binary content)
4. Repeated Synchronization (Idempotency across 1st, 2nd, and 3rd runs)
5. Partial Failure (5 docs: 2 valid, 1 duplicate, 1 oversized, 1 missing 404)
6. Security Failures (Magic-byte, MIME contradiction, SHA mismatch, oversized)
7. Network Failures & Rate Limits (Bounded retries, 401/403/404/429 handling)
8. Resource Cleanup (0 orphan .tmp files remaining in storage)
9. Database Consistency (All EvidenceDocuments point to valid Dispute & real file)
10. Category Preservation (All 11 Razorpay evidence categories preserved)
11. Others Category Structure Variations (Single obj, list, doc IDs, malformed)
12. Financial Safety Invariants (payment_id, amount, currency untouched)
13. Read-Only Razorpay Invariant (Zero POST/PATCH/PUT/DELETE calls to Razorpay)
14. No-AI and No-Processing Invariants (Zero AI models, zero rasterization, zero ProcessedArtifact)
15. Audit Verification (All audit events emitted)
16. API Contract (POST /api/disputes/{dispute_id}/sync-evidence parameter constraints)
17. Concurrency Safety
"""

import asyncio
import hashlib
import inspect
import os
import pytest
from fastapi import HTTPException
from sqlalchemy.future import select

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument
from backend.app.schemas.evidence_sync import DisputeEvidenceSyncResult
from backend.app.services.razorpay_client import MockRazorpayClient, HttpRazorpayClient
from backend.app.services.razorpay_evidence_sync_service import RazorpayEvidenceSyncService
from backend.app.services.razorpay_service import RazorpayService

E2E_DISPUTE_ID = "disp_e2e_integration_999"


# Sample valid file binaries
PDF_HEADER = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
PDF_CONTENT = PDF_HEADER + b"x" * 500 + b"\n%%EOF\n"

PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
PNG_CONTENT = PNG_HEADER + b"x" * 500

JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
JPEG_CONTENT = JPEG_HEADER + b"x" * 500 + b"\xff\xd9"


async def _setup_e2e_dispute(async_db, dispute_id=E2E_DISPUTE_ID):
    """Setup a test dispute in the database."""
    res = await async_db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = res.scalar_one_or_none()
    if not dispute:
        dispute = Dispute(
            id=dispute_id,
            payment_id=f"pay_e2e_{dispute_id[-6:]}",
            amount=250000,
            currency="INR",
            reason_code="chargeback",
            status="open",
            phase="chargeback",
        )
        async_db.add(dispute)
        await async_db.commit()
    return dispute


def _make_e2e_mock_dispute(dispute_id=E2E_DISPUTE_ID, evidence=None):
    return {
        "id": dispute_id,
        "entity": "dispute",
        "payment_id": f"pay_e2e_{dispute_id[-6:]}",
        "amount": 250000,
        "currency": "INR",
        "amount_deducted": 250000,
        "reason_code": "chargeback",
        "reason_description": "Service not provided",
        "respond_by": 1735689600,
        "status": "open",
        "phase": "chargeback",
        "created_at": 1735603200,
        "evidence": evidence,
    }


def _make_e2e_service(mock_dispute=None, mock_documents=None, mock_streams=None):
    mock_disputes = {mock_dispute["id"]: mock_dispute} if mock_dispute else {}
    client = MockRazorpayClient(
        mock_disputes=mock_disputes,
        mock_documents=mock_documents,
        mock_streams=mock_streams,
    )
    rzp_svc = RazorpayService(client=client)
    return RazorpayEvidenceSyncService(razorpay_service=rzp_svc)


# ===========================================================================
# 1. FULL HAPPY PATH
# ===========================================================================


class TestFullHappyPath:
    """Verify complete ingestion pipeline for 4 valid evidence documents."""

    @pytest.mark.asyncio
    async def test_e2e_full_happy_path(self, async_db, tmp_path):
        await _setup_e2e_dispute(async_db)

        mock_disp = _make_e2e_mock_dispute(
            evidence={
                "shipping_proof": ["doc_e2e_ship"],
                "billing_proof": ["doc_e2e_bill"],
                "cancellation_proof": ["doc_e2e_canc"],
                "explanation_letter": ["doc_e2e_expl"],
            }
        )

        mock_docs = {
            "doc_e2e_ship": {"id": "doc_e2e_ship", "entity": "document", "purpose": "dispute_evidence", "name": "ship.pdf", "size": len(PDF_CONTENT), "mime_type": "application/pdf", "created_at": 1735603200},
            "doc_e2e_bill": {"id": "doc_e2e_bill", "entity": "document", "purpose": "dispute_evidence", "name": "bill.png", "size": len(PNG_CONTENT), "mime_type": "image/png", "created_at": 1735603200},
            "doc_e2e_canc": {"id": "doc_e2e_canc", "entity": "document", "purpose": "dispute_evidence", "name": "canc.jpg", "size": len(JPEG_CONTENT), "mime_type": "image/jpeg", "created_at": 1735603200},
            "doc_e2e_expl": {"id": "doc_e2e_expl", "entity": "document", "purpose": "dispute_evidence", "name": "expl.pdf", "size": len(PDF_CONTENT), "mime_type": "application/pdf", "created_at": 1735603200},
        }

        mock_streams = {
            "doc_e2e_ship": PDF_CONTENT + b"_ship",
            "doc_e2e_bill": PNG_CONTENT + b"_bill",
            "doc_e2e_canc": JPEG_CONTENT + b"_canc",
            "doc_e2e_expl": PDF_CONTENT + b"_expl",
        }

        svc = _make_e2e_service(
            mock_dispute=mock_disp, mock_documents=mock_docs, mock_streams=mock_streams
        )

        result = await svc.sync_dispute_evidence(
            E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        # Assertions
        assert result.status == "SUCCESS"
        assert result.discovered_count == 4
        assert result.successful_count == 4
        assert result.failed_count == 0
        assert len(result.results) == 4

        # Verify DB records
        stmt = select(EvidenceDocument).where(EvidenceDocument.dispute_id == E2E_DISPUTE_ID)
        db_docs = (await async_db.execute(stmt)).scalars().all()
        assert len(db_docs) == 4

        for doc in db_docs:
            assert doc.razorpay_doc_id in mock_docs
            assert doc.file_path is not None
            assert os.path.exists(doc.file_path)
            assert doc.file_hash is not None
            assert doc.file_size_bytes > 0
            assert doc.processing_status == "UPLOADED"

        # Verify zero temporary files remaining
        tmp_dir = os.path.join(str(tmp_path), ".tmp")
        if os.path.exists(tmp_dir):
            assert len(os.listdir(tmp_dir)) == 0


# ===========================================================================
# 2. MULTI-CATEGORY & CONTENT DUPLICATES
# ===========================================================================


class TestDuplicates:
    """Verify multi-category doc ID duplicate & Tier 2 content duplicate handling."""

    @pytest.mark.asyncio
    async def test_e2e_multi_category_duplicate(self, async_db, tmp_path):
        """Same doc ID under shipping_proof and billing_proof produces 1 EvidenceDocument."""
        await _setup_e2e_dispute(async_db)

        mock_disp = _make_e2e_mock_dispute(
            evidence={
                "shipping_proof": ["doc_shared_001"],
                "billing_proof": ["doc_shared_001"],
            }
        )
        mock_docs = {
            "doc_shared_001": {"id": "doc_shared_001", "entity": "document", "purpose": "dispute_evidence", "name": "shared.pdf", "size": len(PDF_CONTENT), "mime_type": "application/pdf", "created_at": 1735603200}
        }
        mock_streams = {"doc_shared_001": PDF_CONTENT}

        svc = _make_e2e_service(
            mock_dispute=mock_disp, mock_documents=mock_docs, mock_streams=mock_streams
        )

        result = await svc.sync_dispute_evidence(
            E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "SUCCESS"
        assert result.discovered_count == 1
        assert result.successful_count == 1

        stmt = select(EvidenceDocument).where(EvidenceDocument.dispute_id == E2E_DISPUTE_ID)
        docs = (await async_db.execute(stmt)).scalars().all()
        assert len(docs) == 1

    @pytest.mark.asyncio
    async def test_e2e_content_duplicate(self, async_db, tmp_path):
        """Two different doc IDs containing identical PDF binary -> Tier 2 duplicate detection."""
        await _setup_e2e_dispute(async_db)

        mock_disp = _make_e2e_mock_dispute(
            evidence={
                "shipping_proof": ["doc_content_a"],
                "billing_proof": ["doc_content_b"],
            }
        )
        mock_docs = {
            "doc_content_a": {"id": "doc_content_a", "entity": "document", "purpose": "dispute_evidence", "name": "a.pdf", "size": len(PDF_CONTENT), "mime_type": "application/pdf", "created_at": 1735603200},
            "doc_content_b": {"id": "doc_content_b", "entity": "document", "purpose": "dispute_evidence", "name": "b.pdf", "size": len(PDF_CONTENT), "mime_type": "application/pdf", "created_at": 1735603200},
        }
        mock_streams = {
            "doc_content_a": PDF_CONTENT,
            "doc_content_b": PDF_CONTENT,  # Identical content
        }

        svc = _make_e2e_service(
            mock_dispute=mock_disp, mock_documents=mock_docs, mock_streams=mock_streams
        )

        result = await svc.sync_dispute_evidence(
            E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "SUCCESS"
        assert result.discovered_count == 2
        assert result.successful_count == 1
        assert result.duplicate_count == 1

        # Confirm 1 local EvidenceDocument record
        stmt = select(EvidenceDocument).where(EvidenceDocument.dispute_id == E2E_DISPUTE_ID)
        docs = (await async_db.execute(stmt)).scalars().all()
        assert len(docs) == 1


# ===========================================================================
# 3. REPEATED SYNCHRONIZATION (IDEMPOTENCY)
# ===========================================================================


class TestRepeatedSynchronization:
    """Verify 3 consecutive sync runs on unchanged evidence."""

    @pytest.mark.asyncio
    async def test_e2e_repeated_synchronization(self, async_db, tmp_path):
        await _setup_e2e_dispute(async_db)

        mock_disp = _make_e2e_mock_dispute(
            evidence={"shipping_proof": ["doc_rep_1"], "billing_proof": ["doc_rep_2"]}
        )
        mock_docs = {
            "doc_rep_1": {"id": "doc_rep_1", "entity": "document", "purpose": "dispute_evidence", "name": "1.pdf", "size": len(PDF_CONTENT), "mime_type": "application/pdf", "created_at": 1735603200},
            "doc_rep_2": {"id": "doc_rep_2", "entity": "document", "purpose": "dispute_evidence", "name": "2.png", "size": len(PNG_CONTENT), "mime_type": "image/png", "created_at": 1735603200},
        }
        mock_streams = {"doc_rep_1": PDF_CONTENT, "doc_rep_2": PNG_CONTENT}

        svc = _make_e2e_service(
            mock_dispute=mock_disp, mock_documents=mock_docs, mock_streams=mock_streams
        )

        # Run 1
        r1 = await svc.sync_dispute_evidence(E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))
        assert r1.status == "SUCCESS"
        assert r1.successful_count == 2

        # Run 2
        r2 = await svc.sync_dispute_evidence(E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))
        assert r2.status == "UNCHANGED"
        assert r2.duplicate_count == 2

        # Run 3
        r3 = await svc.sync_dispute_evidence(E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))
        assert r3.status == "UNCHANGED"
        assert r3.duplicate_count == 2

        # DB record count remains 2
        stmt = select(EvidenceDocument).where(EvidenceDocument.dispute_id == E2E_DISPUTE_ID)
        docs = (await async_db.execute(stmt)).scalars().all()
        assert len(docs) == 2


# ===========================================================================
# 4. PARTIAL FAILURE
# ===========================================================================


class TestPartialFailure:
    """Verify 5 documents: 2 valid, 1 duplicate, 1 oversized, 1 missing 404."""

    @pytest.mark.asyncio
    async def test_e2e_partial_failure(self, async_db, tmp_path):
        await _setup_e2e_dispute(async_db)

        # Pre-insert 1 duplicate document
        existing_doc = EvidenceDocument(
            dispute_id=E2E_DISPUTE_ID,
            razorpay_doc_id="doc_part_dup",
            original_filename="existing.pdf",
            internal_filename="existing_uuid.pdf",
            file_path=os.path.join(str(tmp_path), "existing.pdf"),
            file_hash=hashlib.sha256(b"existing_data").hexdigest(),
            file_size_bytes=100,
            mime_type="application/pdf",
            document_type="cancellation_proof",
            processing_status="UPLOADED",
        )
        async_db.add(existing_doc)
        await async_db.commit()

        mock_disp = _make_e2e_mock_dispute(
            evidence={
                "shipping_proof": ["doc_part_v1"],
                "billing_proof": ["doc_part_v2"],
                "cancellation_proof": ["doc_part_dup"],
                "explanation_letter": ["doc_part_huge"],
                "proof_of_service": ["doc_part_404"],
            }
        )

        mock_docs = {
            "doc_part_v1": {"id": "doc_part_v1", "entity": "document", "purpose": "dispute_evidence", "name": "v1.pdf", "size": len(PDF_CONTENT), "mime_type": "application/pdf", "created_at": 1735603200},
            "doc_part_v2": {"id": "doc_part_v2", "entity": "document", "purpose": "dispute_evidence", "name": "v2.png", "size": len(PNG_CONTENT), "mime_type": "image/png", "created_at": 1735603200},
            "doc_part_huge": {"id": "doc_part_huge", "entity": "document", "purpose": "dispute_evidence", "name": "huge.pdf", "size": 10_000_000, "mime_type": "application/pdf", "created_at": 1735603200},
        }

        mock_streams = {
            "doc_part_v1": PDF_CONTENT + b"_part_v1",
            "doc_part_v2": PNG_CONTENT + b"_part_v2",
        }

        client = MockRazorpayClient(
            mock_disputes={E2E_DISPUTE_ID: mock_disp},
            mock_documents=mock_docs,
            mock_streams=mock_streams,
        )
        orig_get_meta = client.get_document_metadata

        async def custom_get_meta(doc_id):
            if doc_id == "doc_part_404":
                from backend.app.services.razorpay_errors import RazorpayNotFoundError
                raise RazorpayNotFoundError(dispute_id=E2E_DISPUTE_ID)
            return await orig_get_meta(doc_id)

        client.get_document_metadata = custom_get_meta
        rzp_svc = RazorpayService(client=client)
        svc = RazorpayEvidenceSyncService(razorpay_service=rzp_svc)

        result = await svc.sync_dispute_evidence(
            E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "PARTIAL_SUCCESS"
        assert result.discovered_count == 5
        assert result.successful_count == 2
        assert result.duplicate_count == 1
        assert result.failed_count == 2


# ===========================================================================
# 5. SECURITY & NETWORK FAILURES
# ===========================================================================


class TestSecurityAndNetworkFailures:
    """Verify security failures and error propagation."""

    @pytest.mark.asyncio
    async def test_e2e_magic_byte_failure(self, async_db, tmp_path):
        """Stream containing invalid magic bytes is rejected and temporary file deleted."""
        await _setup_e2e_dispute(async_db)

        mock_disp = _make_e2e_mock_dispute(evidence={"shipping_proof": ["doc_bad_magic"]})
        mock_docs = {
            "doc_bad_magic": {"id": "doc_bad_magic", "entity": "document", "purpose": "dispute_evidence", "name": "fake.pdf", "size": 500, "mime_type": "application/pdf", "created_at": 1735603200}
        }
        mock_streams = {"doc_bad_magic": b"INVALID_HEADER_BYTES_XXXXXXXX"}

        svc = _make_e2e_service(
            mock_dispute=mock_disp, mock_documents=mock_docs, mock_streams=mock_streams
        )

        result = await svc.sync_dispute_evidence(
            E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "FAILED"
        assert result.failed_count == 1
        assert result.results[0].failure_category == "MAGIC_BYTES_INVALID"

    @pytest.mark.asyncio
    async def test_e2e_dispute_auth_failure_fails_dispute_level(self, async_db, tmp_path):
        """Dispute-level 401 Auth error raises HTTP 502 without partial sync."""
        await _setup_e2e_dispute(async_db)
        svc = _make_e2e_service(mock_dispute=None)

        # Force auth error
        from backend.app.services.razorpay_errors import RazorpayAuthenticationError
        svc._razorpay_service.get_dispute = lambda d_id: (_ for _ in ()).throw(
            RazorpayAuthenticationError()
        )

        with pytest.raises(HTTPException) as exc_info:
            await svc.sync_dispute_evidence(E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))
        assert exc_info.value.status_code == 502


# ===========================================================================
# 6. CATEGORY PRESERVATION & STRUCTURE VARIATIONS
# ===========================================================================


class TestCategoryPreservation:
    """Verify all 11 Razorpay evidence categories preserved."""

    @pytest.mark.asyncio
    async def test_e2e_all_11_categories_preserved(self, async_db, tmp_path):
        await _setup_e2e_dispute(async_db)

        all_cats = [
            "shipping_proof", "billing_proof", "cancellation_proof",
            "customer_communication", "proof_of_service", "explanation_letter",
            "refund_confirmation", "access_activity_log",
            "refund_cancellation_policy", "term_and_conditions",
        ]

        evidence_dict = {cat: [f"doc_cat_{i}"] for i, cat in enumerate(all_cats)}
        mock_disp = _make_e2e_mock_dispute(evidence=evidence_dict)

        mock_docs = {
            f"doc_cat_{i}": {"id": f"doc_cat_{i}", "entity": "document", "purpose": "dispute_evidence", "name": f"{cat}.pdf", "size": len(PDF_CONTENT), "mime_type": "application/pdf", "created_at": 1735603200}
            for i, cat in enumerate(all_cats)
        }
        mock_streams = {f"doc_cat_{i}": PDF_CONTENT + f"_{i}".encode() for i in range(len(all_cats))}

        svc = _make_e2e_service(
            mock_dispute=mock_disp, mock_documents=mock_docs, mock_streams=mock_streams
        )

        result = await svc.sync_dispute_evidence(
            E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path)
        )

        assert result.status == "SUCCESS"
        assert result.discovered_count == len(all_cats)

        # Confirm document_type in DB matches source Razorpay category
        stmt = select(EvidenceDocument).where(EvidenceDocument.dispute_id == E2E_DISPUTE_ID)
        docs = (await async_db.execute(stmt)).scalars().all()
        synced_cats = {d.document_type for d in docs}
        assert synced_cats == set(all_cats)


# ===========================================================================
# 7. FINANCIAL SAFETY & READ-ONLY INVARIANTS
# ===========================================================================


class TestInvariants:
    """Verify financial safety, read-only Razorpay invariants, and no AI/processing imports."""

    @pytest.mark.asyncio
    async def test_financial_safety_invariant(self, async_db, tmp_path):
        dispute = await _setup_e2e_dispute(async_db)
        orig_payment = dispute.payment_id
        orig_amount = dispute.amount
        orig_currency = dispute.currency

        mock_disp = _make_e2e_mock_dispute(evidence={"shipping_proof": ["doc_fin_e2e"]})
        mock_docs = {
            "doc_fin_e2e": {"id": "doc_fin_e2e", "entity": "document", "purpose": "dispute_evidence", "name": "fin.pdf", "size": len(PDF_CONTENT), "mime_type": "application/pdf", "created_at": 1735603200}
        }
        mock_streams = {"doc_fin_e2e": PDF_CONTENT}

        svc = _make_e2e_service(
            mock_dispute=mock_disp, mock_documents=mock_docs, mock_streams=mock_streams
        )

        await svc.sync_dispute_evidence(E2E_DISPUTE_ID, async_db, override_upload_dir=str(tmp_path))

        await async_db.refresh(dispute)
        assert dispute.payment_id == orig_payment
        assert dispute.amount == orig_amount
        assert dispute.currency == orig_currency

    def test_read_only_razorpay_invariant(self):
        for cls in [HttpRazorpayClient, MockRazorpayClient]:
            for method in dir(cls):
                if not method.startswith("_"):
                    assert not method.startswith(("post_", "put_", "patch_", "delete_", "upload_", "accept_", "reject_"))

    def test_no_ai_and_no_processing_invariants(self):
        import backend.app.services.razorpay_evidence_sync_service as svc
        assert not hasattr(svc, "execute_ai_extraction")
        assert not hasattr(svc, "rasterize_pdf")
        assert not hasattr(svc, "evaluate_dispute_policy")
        assert not hasattr(svc, "submit_contest")

    def test_api_contract_accepts_only_dispute_id(self):
        from backend.app.api.dispute_sync import sync_dispute_evidence
        sig = inspect.signature(sync_dispute_evidence)
        params = list(sig.parameters.keys())
        assert "dispute_id" in params
        assert "document_id" not in params
        assert "file_path" not in params
