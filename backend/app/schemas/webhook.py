from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class RazorpayDisputeEntity(BaseModel):
    id: str
    entity: str = "dispute"
    payment_id: str
    amount: int
    currency: str = "INR"
    amount_deducted: int = 0
    reason_code: str
    reason_description: Optional[str] = None
    status: str
    phase: Optional[str] = None
    respond_by: Optional[int] = None
    customer_email: Optional[str] = None
    customer_contact: Optional[str] = None

class RazorpayWebhookPayload(BaseModel):
    entity: str = "event"
    account_id: str
    event: str
    contains: List[str]
    payload: Dict[str, Any]
    created_at: int
