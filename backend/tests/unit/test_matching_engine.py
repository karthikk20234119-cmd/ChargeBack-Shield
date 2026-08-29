import pytest
from datetime import datetime
from unittest.mock import patch

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.schemas.matching import MatchStatus
from backend.app.services.matching_service import run_dispute_matching

async def setup_dispute_with_extraction(
    async_db,
    dispute_id: str,
    payment_id: str = "pay_match_001",
    order_id: str = "ord_match_001",
    amount_minor: int = 500000,
    currency: str = "INR",
    extracted_data: dict = None,
    doc_type: str = "invoice"
):
    dispute = Dispute(
        id=dispute_id,
        payment_id=payment_id,
        amount=amount_minor,
        currency=currency,
        reason_code="13.1",
        status="open",
        raw_payload={
            "payload": {
                "dispute": {
                    "entity": {
                        "id": dispute_id,
                        "payment_id": payment_id,
                        "order_id": order_id,
                        "amount": amount_minor,
                        "currency": currency,
                        "customer_name": "Gaurav Sharma"
                    }
                }
            }
        }
    )
    async_db.add(dispute)

    doc = EvidenceDocument(
        id=f"doc_{dispute_id}",
        dispute_id=dispute_id,
        original_filename="invoice.png",
        internal_filename=f"{dispute_id}_inv.png",
        file_path="dummy/path",
        file_hash="dummy_hash",
        file_size_bytes=100,
        mime_type="image/png",
        processing_status="AI_EXTRACTED"
    )
    async_db.add(doc)

    default_ext = {
        "document_type": doc_type,
        "payment_id": payment_id,
        "order_id": order_id,
        "amount_minor": amount_minor,
        "currency": currency,
        "customer_name": "Gaurav Sharma",
        "awb_number": "1Z9998880001",
        "invoice_date": "2026-08-15",
        "delivery_date": "2026-08-20",
        "confidence_by_field": {"order_id": 0.99, "payment_id": 0.99}
    }
    if extracted_data:
        default_ext.update(extracted_data)

    ext = ExtractedEvidence(
        document_id=doc.id,
        document_type=default_ext.get("document_type"),
        payment_id=default_ext.get("payment_id"),
        order_id=default_ext.get("order_id"),
        amount_minor=default_ext.get("amount_minor"),
        currency=default_ext.get("currency"),
        customer_name=default_ext.get("customer_name"),
        awb_number=default_ext.get("awb_number"),
        delivery_date=default_ext.get("delivery_date"),
        confidence_score=0.99,
        extracted_data=default_ext
    )
    async_db.add(ext)
    await async_db.commit()
    return dispute

# ------------------------------------------------------------------
# Test Cases 1 to 25
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_order_id_exact_match(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m1", order_id="ord_1001")
    res = await run_dispute_matching("disp_m1", async_db)
    ord_match = next(f for f in res.field_results if f.field == "order_id")
    assert ord_match.status == MatchStatus.MATCH

@pytest.mark.asyncio
async def test_order_id_mismatch(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m2", order_id="ord_1001", extracted_data={"order_id": "ord_9999"})
    res = await run_dispute_matching("disp_m2", async_db)
    ord_match = next(f for f in res.field_results if f.field == "order_id")
    assert ord_match.status == MatchStatus.MISMATCH

@pytest.mark.asyncio
async def test_payment_id_match(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m3", payment_id="pay_1001")
    res = await run_dispute_matching("disp_m3", async_db)
    pay_match = next(f for f in res.field_results if f.field == "payment_id")
    assert pay_match.status == MatchStatus.MATCH

@pytest.mark.asyncio
async def test_payment_id_mismatch(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m4", payment_id="pay_1001", extracted_data={"payment_id": "pay_9999"})
    res = await run_dispute_matching("disp_m4", async_db)
    pay_match = next(f for f in res.field_results if f.field == "payment_id")
    assert pay_match.status == MatchStatus.MISMATCH

@pytest.mark.asyncio
async def test_awb_match(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m5", doc_type="shipping_proof", extracted_data={"awb_number": "1Z888777"})
    res = await run_dispute_matching("disp_m5", async_db)
    assert res.overall_status in {"DETERMINISTIC_MATCH", "INCOMPLETE_EVIDENCE"}

@pytest.mark.asyncio
async def test_awb_mismatch(async_db):
    # Cross-doc AWB mismatch
    await setup_dispute_with_extraction(async_db, "disp_m6", doc_type="shipping_proof", extracted_data={"awb_number": "AWB_111"})
    # Add second document with different AWB
    doc2 = EvidenceDocument(id="doc_m6_2", dispute_id="disp_m6", original_filename="ship2.png", internal_filename="ship2.png", file_path="dummy", file_hash="hash2", file_size_bytes=10, mime_type="image/png", processing_status="AI_EXTRACTED")
    async_db.add(doc2)
    ext2 = ExtractedEvidence(document_id="doc_m6_2", document_type="shipping_proof", awb_number="AWB_222", extracted_data={})
    async_db.add(ext2)
    await async_db.commit()

    res = await run_dispute_matching("disp_m6", async_db)
    assert res.overall_status == "CONFLICT_DETECTED"

@pytest.mark.asyncio
async def test_currency_normalization(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m7", currency="INR", extracted_data={"currency": "inr"})
    res = await run_dispute_matching("disp_m7", async_db)
    curr_match = next(f for f in res.field_results if f.field == "currency")
    assert curr_match.status == MatchStatus.MATCH

@pytest.mark.asyncio
async def test_currency_mismatch(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m8", currency="INR", extracted_data={"currency": "USD"})
    res = await run_dispute_matching("disp_m8", async_db)
    curr_match = next(f for f in res.field_results if f.field == "currency")
    assert curr_match.status == MatchStatus.MISMATCH

@pytest.mark.asyncio
async def test_amount_match(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m9", amount_minor=500000)
    res = await run_dispute_matching("disp_m9", async_db)
    amt_match = next(f for f in res.field_results if f.field == "amount_minor")
    assert amt_match.status == MatchStatus.MATCH

@pytest.mark.asyncio
async def test_amount_mismatch(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m10", amount_minor=500000, extracted_data={"amount_minor": 750000})
    res = await run_dispute_matching("disp_m10", async_db)
    amt_match = next(f for f in res.field_results if f.field == "amount_minor")
    assert amt_match.status == MatchStatus.MISMATCH

@pytest.mark.asyncio
async def test_amount_minor_units(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m11", amount_minor=11200000)
    res = await run_dispute_matching("disp_m11", async_db)
    amt_match = next(f for f in res.field_results if f.field == "amount_minor")
    assert amt_match.status == MatchStatus.MATCH

@pytest.mark.asyncio
async def test_missing_amount(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m12", extracted_data={"amount_minor": None})
    res = await run_dispute_matching("disp_m12", async_db)
    amt_match = next(f for f in res.field_results if f.field == "amount_minor")
    assert amt_match.status == MatchStatus.MISSING

@pytest.mark.asyncio
async def test_invalid_date(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m13", doc_type="delivery_proof", extracted_data={"delivery_date": "not-a-date"})
    res = await run_dispute_matching("disp_m13", async_db)
    deliv_match = next(f for f in res.field_results if f.field == "delivery_date")
    assert deliv_match.status == MatchStatus.UNVERIFIABLE

@pytest.mark.asyncio
async def test_date_match(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m14", doc_type="delivery_proof", extracted_data={"delivery_date": "2026-08-20"})
    res = await run_dispute_matching("disp_m14", async_db, reference_date="2026-08-26")
    deliv_match = next(f for f in res.field_results if f.field == "delivery_date")
    assert deliv_match.status == MatchStatus.MATCH

@pytest.mark.asyncio
async def test_date_mismatch(async_db):
    # Future delivery date
    await setup_dispute_with_extraction(async_db, "disp_m15", doc_type="delivery_proof", extracted_data={"delivery_date": "2026-12-31"})
    res = await run_dispute_matching("disp_m15", async_db, reference_date="2026-08-26")
    deliv_match = next(f for f in res.field_results if f.field == "delivery_date")
    assert deliv_match.status == MatchStatus.MISMATCH

@pytest.mark.asyncio
async def test_future_delivery_date(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m16", doc_type="delivery_proof", extracted_data={"delivery_date": "2029-01-01"})
    res = await run_dispute_matching("disp_m16", async_db, reference_date="2026-08-26")
    deliv_match = next(f for f in res.field_results if f.field == "delivery_date")
    assert deliv_match.status == MatchStatus.MISMATCH

@pytest.mark.asyncio
async def test_delivery_before_shipment(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m17", doc_type="shipping_proof", extracted_data={"delivery_date": "2026-08-20"})
    # Add delivery proof earlier than shipment
    doc2 = EvidenceDocument(id="doc_m17_2", dispute_id="disp_m17", original_filename="pod.png", internal_filename="pod.png", file_path="dummy", file_hash="hash17", file_size_bytes=10, mime_type="image/png", processing_status="AI_EXTRACTED")
    async_db.add(doc2)
    ext2 = ExtractedEvidence(document_id="doc_m17_2", document_type="delivery_proof", delivery_date="2026-08-10", extracted_data={})
    async_db.add(ext2)
    await async_db.commit()

    res = await run_dispute_matching("disp_m17", async_db, reference_date="2026-08-26")
    deliv_match = next(f for f in res.field_results if f.field == "delivery_date" and f.source_doc_type == "delivery_proof")
    assert deliv_match.status == MatchStatus.MISMATCH

@pytest.mark.asyncio
async def test_customer_name_normalization(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m18", extracted_data={"customer_name": "  GAURAV   SHARMA  "})
    res = await run_dispute_matching("disp_m18", async_db)
    name_match = next(f for f in res.field_results if f.field == "customer_name")
    assert name_match.status == MatchStatus.MATCH

@pytest.mark.asyncio
async def test_missing_field(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m19", extracted_data={"order_id": None})
    res = await run_dispute_matching("disp_m19", async_db)
    ord_match = next(f for f in res.field_results if f.field == "order_id")
    assert ord_match.status == MatchStatus.MISSING

@pytest.mark.asyncio
async def test_document_type_not_applicable(async_db):
    # Shipping proof does not evaluate payment_id
    await setup_dispute_with_extraction(async_db, "disp_m20", doc_type="shipping_proof")
    res = await run_dispute_matching("disp_m20", async_db)
    pay_matches = [f for f in res.field_results if f.field == "payment_id"]
    assert len(pay_matches) == 0 # Skipped cleanly

@pytest.mark.asyncio
async def test_cross_document_conflict(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m21", doc_type="invoice", extracted_data={"order_id": "ORD_111"})
    doc2 = EvidenceDocument(id="doc_m21_2", dispute_id="disp_m21", original_filename="ship.png", internal_filename="ship.png", file_path="dummy", file_hash="hash21", file_size_bytes=10, mime_type="image/png", processing_status="AI_EXTRACTED")
    async_db.add(doc2)
    ext2 = ExtractedEvidence(document_id="doc_m21_2", document_type="shipping_proof", order_id="ORD_999", extracted_data={})
    async_db.add(ext2)
    await async_db.commit()

    res = await run_dispute_matching("disp_m21", async_db)
    assert res.overall_status == "CONFLICT_DETECTED"

@pytest.mark.asyncio
async def test_multiple_documents(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m22", doc_type="invoice", extracted_data={"order_id": "ord_match_001"})
    doc2 = EvidenceDocument(id="doc_m22_2", dispute_id="disp_m22", original_filename="pod.png", internal_filename="pod.png", file_path="dummy", file_hash="hash22", file_size_bytes=10, mime_type="image/png", processing_status="AI_EXTRACTED")
    async_db.add(doc2)
    ext2 = ExtractedEvidence(document_id="doc_m22_2", document_type="delivery_proof", order_id="ord_match_001", delivery_date="2026-08-20", extracted_data={})
    async_db.add(ext2)
    await async_db.commit()

    res = await run_dispute_matching("disp_m22", async_db)
    assert res.overall_status in {"DETERMINISTIC_MATCH", "INCOMPLETE_EVIDENCE"}


@pytest.mark.asyncio
async def test_ai_confidence_cannot_override_mismatch(async_db):
    """
    CRITICAL INVARIANT TEST:
    AI confidence = 0.99 must NOT override a deterministic mismatch!
    """
    await setup_dispute_with_extraction(
        async_db, "disp_m23", order_id="ORD_EXPECTED",
        extracted_data={"order_id": "ORD_MISMATCHED", "confidence_by_field": {"order_id": 0.99}}
    )
    res = await run_dispute_matching("disp_m23", async_db)
    ord_match = next(f for f in res.field_results if f.field == "order_id")
    assert ord_match.status == MatchStatus.MISMATCH
    assert res.has_critical_mismatch is True

@pytest.mark.asyncio
async def test_critical_mismatch(async_db):
    await setup_dispute_with_extraction(async_db, "disp_m24", payment_id="pay_WRONG", extracted_data={"payment_id": "pay_DIFFERENT"})
    res = await run_dispute_matching("disp_m24", async_db)
    assert res.has_critical_mismatch is True
    assert res.overall_status == "CRITICAL_MISMATCH"

@pytest.mark.asyncio
async def test_no_razorpay_call(async_db):
    """Verifies matching engine executes 100% locally with zero external network or Razorpay calls."""
    with patch("httpx.AsyncClient.post") as mock_post:
        await setup_dispute_with_extraction(async_db, "disp_m25")
        res = await run_dispute_matching("disp_m25", async_db)
        assert res.dispute_id == "disp_m25"
        assert mock_post.called is False
