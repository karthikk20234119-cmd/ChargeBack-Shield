import hmac
import hashlib
import json
import pytest
from backend.app.config import settings
from backend.app.utils.security import verify_razorpay_signature

def generate_signature(payload_bytes: bytes, secret: str = None) -> str:
    secret_key = secret or settings.RAZORPAY_WEBHOOK_SECRET or "samplesecretkey123456"
    return hmac.new(
        key=secret_key.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()

def make_dispute_payload(dispute_id: str = "disp_test_001", amount: int = 500000) -> dict:
    return {
        "entity": "event",
        "account_id": "acc_123",
        "event": "payment.dispute.created",
        "contains": ["dispute"],
        "payload": {
            "dispute": {
                "entity": {
                    "id": dispute_id,
                    "entity": "dispute",
                    "payment_id": "pay_test_001",
                    "amount": amount,
                    "currency": "INR",
                    "amount_deducted": amount,
                    "reason_code": "13.1",
                    "reason_description": "Merchandise/Services Not Received",
                    "status": "open",
                    "phase": "chargeback",
                    "respond_by": 1770000000
                }
            }
        },
        "created_at": 1769000000
    }

# ------------------------------------------------------------------
# Security Unit Tests
# ------------------------------------------------------------------

def test_verify_razorpay_signature_valid():
    secret = "test_webhook_secret_123"
    raw_body = b'{"event": "payment.dispute.created"}'
    sig = generate_signature(raw_body, secret)
    assert verify_razorpay_signature(raw_body, sig, secret) is True

def test_verify_razorpay_signature_tampered():
    secret = "test_webhook_secret_123"
    raw_body = b'{"event": "payment.dispute.created"}'
    sig = generate_signature(raw_body, secret)
    tampered_body = b'{"event": "payment.dispute.created", "tampered": true}'
    assert verify_razorpay_signature(tampered_body, sig, secret) is False

# ------------------------------------------------------------------
# Webhook Verification Test Suite (TEST A through TEST G)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_test_a_valid_signature_new_event(client):
    """TEST A: Valid signature + new event -> HTTP 200 -> dispute created"""
    payload = make_dispute_payload("disp_test_a")
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = generate_signature(body_bytes)
    headers = {
        "x-razorpay-signature": sig,
        "x-razorpay-event-id": "evt_test_a_001"
    }

    response = await client.post("/api/webhooks/razorpay", content=body_bytes, headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["dispute_id"] == "disp_test_a"

    # Verify dispute exists in database via API
    get_res = await client.get("/api/disputes/disp_test_a")
    assert get_res.status_code == 200
    assert get_res.json()["amount"] == 500000

@pytest.mark.asyncio
async def test_webhook_test_b_same_event_id_sent_twice(client):
    """TEST B: Same event ID sent twice -> second event does not create duplicate data"""
    payload = make_dispute_payload("disp_test_b")
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = generate_signature(body_bytes)
    headers = {
        "x-razorpay-signature": sig,
        "x-razorpay-event-id": "evt_test_b_duplicate"
    }

    # First delivery
    res1 = await client.post("/api/webhooks/razorpay", content=body_bytes, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "success"

    # Second delivery (Duplicate event ID)
    res2 = await client.post("/api/webhooks/razorpay", content=body_bytes, headers=headers)
    assert res2.status_code == 200
    assert "Duplicate event ID ignored" in res2.json()["message"]

@pytest.mark.asyncio
async def test_webhook_test_c_same_dispute_different_event_id(client):
    """TEST C: Same dispute ID but different event ID -> behavior is explicitly defined and safe (state updated idempotently)"""
    payload1 = make_dispute_payload("disp_test_c")
    body_bytes1 = json.dumps(payload1).encode("utf-8")
    sig1 = generate_signature(body_bytes1)
    headers1 = {
        "x-razorpay-signature": sig1,
        "x-razorpay-event-id": "evt_test_c_001"
    }

    res1 = await client.post("/api/webhooks/razorpay", content=body_bytes1, headers=headers1)
    assert res1.status_code == 200

    # Second event for same dispute but updated status (e.g. payment.dispute.under_review)
    payload2 = make_dispute_payload("disp_test_c")
    payload2["event"] = "payment.dispute.under_review"
    payload2["payload"]["dispute"]["entity"]["status"] = "under_review"
    
    body_bytes2 = json.dumps(payload2).encode("utf-8")
    sig2 = generate_signature(body_bytes2)
    headers2 = {
        "x-razorpay-signature": sig2,
        "x-razorpay-event-id": "evt_test_c_002"
    }

    res2 = await client.post("/api/webhooks/razorpay", content=body_bytes2, headers=headers2)
    assert res2.status_code == 200
    assert res2.json()["message"] == "Dispute updated idempotently"

    # Verify updated state
    get_res = await client.get("/api/disputes/disp_test_c")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "under_review"

@pytest.mark.asyncio
async def test_webhook_test_d_invalid_signature(client):
    """TEST D: Invalid signature -> request rejected (HTTP 401) -> no database mutation"""
    payload = make_dispute_payload("disp_test_d")
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "x-razorpay-signature": "invalid_signature_hash_123456",
        "x-razorpay-event-id": "evt_test_d_001"
    }

    response = await client.post("/api/webhooks/razorpay", content=body_bytes, headers=headers)
    assert response.status_code == 401

    # Verify no dispute was created in database
    get_res = await client.get("/api/disputes/disp_test_d")
    assert get_res.status_code == 404

@pytest.mark.asyncio
async def test_webhook_test_e_missing_signature(client):
    """TEST E: Missing signature -> request rejected (HTTP 401) -> no database mutation"""
    payload = make_dispute_payload("disp_test_e")
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "x-razorpay-event-id": "evt_test_e_001"
    }

    response = await client.post("/api/webhooks/razorpay", content=body_bytes, headers=headers)
    assert response.status_code == 401

    # Verify no dispute was created
    get_res = await client.get("/api/disputes/disp_test_e")
    assert get_res.status_code == 404

@pytest.mark.asyncio
async def test_webhook_test_f_malformed_json_with_valid_signature(client):
    """TEST F: Malformed JSON with valid signature -> safe error (HTTP 400) -> no partial database mutation"""
    malformed_bytes = b'{"event": "payment.dispute.created", "payload": { invalid json }'
    sig = generate_signature(malformed_bytes)
    headers = {
        "x-razorpay-signature": sig,
        "x-razorpay-event-id": "evt_test_f_001"
    }

    response = await client.post("/api/webhooks/razorpay", content=malformed_bytes, headers=headers)
    assert response.status_code == 400
    assert "Malformed JSON payload" in response.json()["detail"]

@pytest.mark.asyncio
async def test_webhook_test_g_unknown_webhook_event(client):
    """TEST G: Unknown webhook event -> safely ignored (HTTP 200) -> no unintended financial action"""
    payload = {
        "entity": "event",
        "account_id": "acc_123",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_captured_001",
                    "amount": 500000
                }
            }
        },
        "created_at": 1769000000
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = generate_signature(body_bytes)
    headers = {
        "x-razorpay-signature": sig,
        "x-razorpay-event-id": "evt_test_g_001"
    }

    response = await client.post("/api/webhooks/razorpay", content=body_bytes, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
