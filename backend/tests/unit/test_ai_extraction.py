import os
import json
import pytest
from unittest.mock import patch
from PIL import Image
from sqlalchemy.future import select

from backend.app.models.dispute import Dispute
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.processed_artifact import ProcessedArtifact
from backend.app.schemas.extraction import ExtractedFactSchema
from backend.app.services.ai_provider import MockAIProvider
from backend.app.services.ai_extraction_service import execute_ai_extraction

async def create_ready_for_ai_document(async_db, dispute_id: str, doc_id: str, tmp_path):
    upload_dir = str(tmp_path / "uploads")
    processed_dir = str(tmp_path / "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # Dispute
    stmt = select(Dispute).where(Dispute.id == dispute_id)
    res = await async_db.execute(stmt)
    dispute = res.scalar_one_or_none()
    if not dispute:
        dispute = Dispute(id=dispute_id, payment_id="pay_synth_0001", amount=500000, reason_code="13.1", status="open", raw_payload={"dispute_id": dispute_id})
        async_db.add(dispute)


    # File
    file_path = os.path.join(upload_dir, f"{doc_id}_invoice.png")
    img = Image.new("RGB", (100, 100), "white")
    img.save(file_path, "PNG")

    doc = EvidenceDocument(
        id=doc_id,
        dispute_id=dispute_id,
        original_filename="invoice.png",
        internal_filename=f"{doc_id}_invoice.png",
        file_path=file_path,
        file_hash="dummy_hash_123",
        file_size_bytes=100,
        mime_type="image/png",
        processing_status="READY_FOR_AI"
    )
    async_db.add(doc)

    # Processed Artifact Page
    page_dir = os.path.join(processed_dir, doc_id)
    os.makedirs(page_dir, exist_ok=True)
    page_path = os.path.join(page_dir, "page_001.png")
    img.save(page_path, "PNG")

    art = ProcessedArtifact(
        evidence_id=doc_id,
        page_number=1,
        file_path=page_path,
        width=100,
        height=100,
        file_size_bytes=100,
        format="PNG",
        source_document_type="png"
    )
    async_db.add(art)
    await async_db.commit()
    return doc

async def execute_ai_extraction_helper(async_db, evidence_id: str, provider):
    try:
        res_dict = await execute_ai_extraction(evidence_id=evidence_id, db=async_db, provider=provider)
        class MockResponse:
            status_code = 200
            def json(self): return res_dict
        return MockResponse()
    except Exception as exc:
        status_code = getattr(exc, "status_code", 500)
        detail = getattr(exc, "detail", str(exc))
        class MockErrorResponse:
            def __init__(self, code, det):
                self.status_code = code
                self.detail = det
            def json(self): return {"detail": self.detail}
        return MockErrorResponse(status_code, detail)

# ------------------------------------------------------------------
# Test Cases (1 to 17)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_invoice_extraction(client, async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_1", "doc_inv_1", tmp_path)
    res = await client.post(f"/api/evidence/{doc.id}/extract?document_hint=invoice")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "AI_EXTRACTED"
    assert data["document_type"] == "invoice"
    assert data["extracted_data"]["order_id"] == "ord_synth_0001"
    assert data["extracted_data"]["amount_minor"] in {500000, 9030000}


@pytest.mark.asyncio
async def test_valid_shipping_extraction(client, async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_2", "doc_ship_1", tmp_path)
    res = await client.post(f"/api/evidence/{doc.id}/extract?document_hint=shipping_proof")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "AI_EXTRACTED"
    assert data["document_type"] == "shipping_proof"
    assert data["extracted_data"]["awb_number"] == "1Z9998880001"

@pytest.mark.asyncio
async def test_valid_delivery_extraction(client, async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_3", "doc_deliv_1", tmp_path)
    res = await client.post(f"/api/evidence/{doc.id}/extract?document_hint=delivery_proof")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "AI_EXTRACTED"
    assert data["document_type"] == "delivery_proof"
    assert data["extracted_data"]["signature_present"] is True

@pytest.mark.asyncio
async def test_missing_fields(client, async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_4", "doc_missing_1", tmp_path)
    res = await client.post(f"/api/evidence/{doc.id}/extract?document_hint=shipping_proof")
    assert res.status_code == 200
    data = res.json()
    assert data["extracted_data"]["amount_minor"] is None

@pytest.mark.asyncio
async def test_invalid_schema(async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_5", "doc_schema_err", tmp_path)
    provider = MockAIProvider(mock_scenario="invalid_schema")

    res = await execute_ai_extraction_helper(async_db, doc.id, provider)
    assert res.status_code == 400
    assert "schema validation" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_malformed_ai_json(async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_6", "doc_json_err", tmp_path)
    provider = MockAIProvider(mock_scenario="malformed_json")

    res = await execute_ai_extraction_helper(async_db, doc.id, provider)
    assert res.status_code in [400, 500]


@pytest.mark.asyncio
async def test_unknown_document_type(client, async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_7", "doc_unk_1", tmp_path)
    res = await client.post(f"/api/evidence/{doc.id}/extract?document_hint=unknown")
    assert res.status_code == 200
    data = res.json()
    assert data["document_type"] == "unknown"
    assert "Unrecognized document layout" in data["extracted_data"]["extraction_warnings"]

@pytest.mark.asyncio
async def test_invalid_amount(async_db, tmp_path):
    schema = ExtractedFactSchema(document_type="invoice", amount_minor=None)
    assert schema.amount_minor is None

@pytest.mark.asyncio
async def test_invalid_date(async_db, tmp_path):
    schema = ExtractedFactSchema(document_type="invoice", delivery_date="invalid-date")
    assert schema.delivery_date == "invalid-date"

@pytest.mark.asyncio
async def test_prompt_injection(client, async_db, tmp_path):
    """
    CRITICAL INVARIANT TEST:
    Verifies that an adversarial document containing prompt injection
    does NOT output financial decision fields (ALLOW / REJECT / HUMAN_REVIEW).
    """
    doc = await create_ready_for_ai_document(async_db, "disp_ai_8", "doc_inj_1", tmp_path)
    res = await client.post(f"/api/evidence/{doc.id}/extract?document_hint=prompt_injection")
    assert res.status_code == 200
    data = res.json()
    
    assert "decision" not in data["extracted_data"]
    assert "outcome" not in data["extracted_data"]
    assert "ALLOW" not in data["extracted_data"].values()
    assert "REJECT" not in data["extracted_data"].values()
    assert data["status"] == "AI_EXTRACTED"

@pytest.mark.asyncio
async def test_mock_provider(async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_9", "doc_mock_1", tmp_path)
    provider = MockAIProvider()
    res = await execute_ai_extraction_helper(async_db, doc.id, provider)
    assert res.status_code == 200
    assert res.json()["status"] == "AI_EXTRACTED"

@pytest.mark.asyncio
async def test_provider_timeout(async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_10", "doc_timeout_1", tmp_path)
    provider = MockAIProvider(mock_scenario="timeout")
    res = await execute_ai_extraction_helper(async_db, doc.id, provider)
    assert res.status_code == 500
    assert "timed out" in res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_provider_failure(async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_11", "doc_fail_1", tmp_path)
    provider = MockAIProvider(mock_scenario="failure")
    res = await execute_ai_extraction_helper(async_db, doc.id, provider)
    assert res.status_code == 500

@pytest.mark.asyncio
async def test_pydantic_validation(async_db, tmp_path):
    raw = {"document_type": "INVOICE", "amount_minor": 1000, "currency": "inr"}
    fact = ExtractedFactSchema(**raw)
    assert fact.document_type == "invoice"
    assert fact.currency == "INR"

@pytest.mark.asyncio
async def test_extraction_status_success(client, async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_12", "doc_succ_1", tmp_path)
    res = await client.post(f"/api/evidence/{doc.id}/extract")
    assert res.status_code == 200
    assert res.json()["status"] == "AI_EXTRACTED"

    doc_stmt = select(EvidenceDocument).where(EvidenceDocument.id == doc.id)
    doc_res = await async_db.execute(doc_stmt)
    assert doc_res.scalar_one().processing_status == "AI_EXTRACTED"

@pytest.mark.asyncio
async def test_extraction_status_failure(async_db, tmp_path):
    doc = await create_ready_for_ai_document(async_db, "disp_ai_13", "doc_fail_2", tmp_path)
    provider = MockAIProvider(mock_scenario="failure")
    await execute_ai_extraction_helper(async_db, doc.id, provider)

    doc_stmt = select(EvidenceDocument).where(EvidenceDocument.id == doc.id)
    doc_res = await async_db.execute(doc_stmt)
    assert doc_res.scalar_one().processing_status == "AI_EXTRACTION_FAILED"

@pytest.mark.asyncio
async def test_ground_truth_not_accessed(client, async_db, tmp_path):
    """Verifies extraction pipeline never opens dataset/ground_truth/ files."""
    doc = await create_ready_for_ai_document(async_db, "disp_ai_14", "doc_no_gt", tmp_path)

    with patch("builtins.open", wraps=open) as mock_open:
        res = await client.post(f"/api/evidence/{doc.id}/extract")
        assert res.status_code == 200

        for call_item in mock_open.call_args_list:
            filepath = str(call_item[0][0])
            assert "ground_truth" not in filepath


@pytest.mark.asyncio
async def test_groq_provider_missing_key():
    from backend.app.services.ai_provider import GroqProvider, ProcessedPageInput
    provider = GroqProvider(api_key="")
    pages = [ProcessedPageInput(page_number=1, image_path="nonexistent.png", width=100, height=100)]
    with pytest.raises(ValueError, match="Groq API key is not configured"):
        await provider.extract_evidence(pages)


@pytest.mark.asyncio
async def test_groq_provider_initialization():
    from backend.app.services.ai_provider import GroqProvider
    provider = GroqProvider(model_name="llama-3.2-11b-vision-preview", api_key="gsk_test_key_123")
    assert provider.model_name == "llama-3.2-11b-vision-preview"
    assert provider.api_key == "gsk_test_key_123"


@pytest.mark.asyncio
async def test_groq_provider_extract_evidence_success(tmp_path):
    from backend.app.services.ai_provider import GroqProvider, ProcessedPageInput
    from unittest.mock import AsyncMock, MagicMock

    img_path = str(tmp_path / "page_001.png")
    img = Image.new("RGB", (100, 100), "white")
    img.save(img_path, "PNG")

    provider = GroqProvider(api_key="gsk_test_key_123")
    pages = [ProcessedPageInput(page_number=1, image_path=img_path, width=100, height=100)]

    mock_msg = MagicMock()
    mock_msg.content = json.dumps({
        "document_type": "invoice",
        "payment_id": "pay_test123",
        "amount_minor": 50000
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch("groq.AsyncGroq", return_value=mock_client):
        result = await provider.extract_evidence(pages)
        assert result["document_type"] == "invoice"
        assert result["payment_id"] == "pay_test123"


@pytest.mark.asyncio
async def test_groq_provider_malformed_json(tmp_path):
    from backend.app.services.ai_provider import GroqProvider, ProcessedPageInput
    from unittest.mock import AsyncMock, MagicMock

    img_path = str(tmp_path / "page_001.png")
    img = Image.new("RGB", (100, 100), "white")
    img.save(img_path, "PNG")

    provider = GroqProvider(api_key="gsk_test_key_123")
    pages = [ProcessedPageInput(page_number=1, image_path=img_path, width=100, height=100)]

    mock_msg = MagicMock()
    mock_msg.content = "INVALID_NON_JSON_RESPONSE"
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch("groq.AsyncGroq", return_value=mock_client):
        with pytest.raises(ValueError, match="malformed non-JSON payload"):
            await provider.extract_evidence(pages)

