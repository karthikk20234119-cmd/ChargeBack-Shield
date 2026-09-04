import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Header, Depends, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.dispute import Dispute
from backend.app.models.webhook_event import WebhookEvent
from backend.app.utils.security import verify_razorpay_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

@router.post("/razorpay")
async def razorpay_webhook_listener(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="x-razorpay-signature"),
    x_razorpay_event_id: str = Header(None, alias="x-razorpay-event-id"),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests Razorpay webhook events (e.g. payment.dispute.created).
    Verifies HMAC-SHA256 signature using raw request body bytes BEFORE JSON parsing.
    Enforces idempotency via x-razorpay-event-id and dispute entity state updates.
    """
    # 1. Read Raw Body FIRST
    raw_body = await request.body()

    secret = settings.RAZORPAY_WEBHOOK_SECRET or "samplesecretkey123456"
    if not x_razorpay_signature or not verify_razorpay_signature(raw_body, x_razorpay_signature, secret):
        logger.warning("Rejected webhook: missing or invalid x-razorpay-signature header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing x-razorpay-signature header"
        )

    # 3. JSON Parsing ONLY AFTER Signature Verification
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        logger.error("Failed to parse verified webhook payload JSON.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON payload")

    event_type = data.get("event")
    
    # 4. Check Webhook Event Idempotency using x-razorpay-event-id
    effective_event_id = x_razorpay_event_id or data.get("account_id", "") + "_" + str(data.get("created_at", ""))
    
    if effective_event_id:
        evt_stmt = select(WebhookEvent).where(WebhookEvent.event_id == effective_event_id)
        evt_res = await db.execute(evt_stmt)
        if evt_res.scalar_one_or_none():
            logger.info(f"Duplicate webhook event ID {effective_event_id} ignored idempotently.")
            return {"status": "success", "message": "Duplicate event ID ignored idempotently", "event_id": effective_event_id}

    # Record event ID in WebhookEvent table
    dispute_entity = data.get("payload", {}).get("dispute", {}).get("entity", {})
    dispute_id = dispute_entity.get("id") if dispute_entity else None

    if effective_event_id:
        db_event = WebhookEvent(
            event_id=effective_event_id,
            event_type=event_type or "unknown",
            dispute_id=dispute_id,
            payload=data
        )
        db.add(db_event)

    # 5. Process Supported Dispute Events
    supported_dispute_events = [
        "payment.dispute.created",
        "payment.dispute.under_review",
        "payment.dispute.action_required",
        "payment.dispute.won",
        "payment.dispute.lost",
        "payment.dispute.closed"
    ]

    if event_type not in supported_dispute_events or not dispute_id:
        await db.commit()
        logger.info(f"Webhook event {event_type} logged; no dispute action taken.")
        return {"status": "ignored", "reason": f"Event {event_type} not handled as active dispute entity"}

    # 6. Idempotent Dispute Table Creation/Update
    stmt = select(Dispute).where(Dispute.id == dispute_id)
    result = await db.execute(stmt)
    existing_dispute = result.scalar_one_or_none()

    if existing_dispute:
        existing_dispute.status = dispute_entity.get("status", existing_dispute.status)
        existing_dispute.phase = dispute_entity.get("phase", existing_dispute.phase)
        existing_dispute.raw_payload = data
        await db.commit()
        logger.info(f"Updated existing dispute record idempotently: {dispute_id}")
        return {"status": "success", "message": "Dispute updated idempotently", "dispute_id": dispute_id}

    respond_by_raw = dispute_entity.get("respond_by")
    respond_by_dt = None
    if isinstance(respond_by_raw, (int, float)):
        try:
            respond_by_dt = datetime.fromtimestamp(respond_by_raw)
        except Exception:
            respond_by_dt = None
    elif isinstance(respond_by_raw, datetime):
        respond_by_dt = respond_by_raw

    new_dispute = Dispute(
        id=dispute_id,
        entity=dispute_entity.get("entity", "dispute"),
        payment_id=dispute_entity.get("payment_id", ""),
        amount=dispute_entity.get("amount", 0),
        currency=dispute_entity.get("currency", "INR"),
        amount_deducted=dispute_entity.get("amount_deducted", 0),
        reason_code=dispute_entity.get("reason_code", "13.1"),
        reason_description=dispute_entity.get("reason_description"),
        status=dispute_entity.get("status", "open"),
        phase=dispute_entity.get("phase"),
        respond_by=respond_by_dt,
        customer_email=dispute_entity.get("customer_email"),
        customer_contact=dispute_entity.get("customer_contact"),
        raw_payload=data
    )

    db.add(new_dispute)
    await db.commit()
    logger.info(f"Created new dispute record: {dispute_id}")
    return {"status": "success", "message": "Dispute created successfully", "dispute_id": dispute_id}
