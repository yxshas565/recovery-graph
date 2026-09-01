# backend/webhook/models.py
from pydantic import BaseModel
from typing import Optional, Any

class RazorpayPaymentEntity(BaseModel):
    id: str
    entity: str = "payment"
    amount: int
    currency: str = "INR"
    status: str
    order_id: Optional[str] = None
    method: Optional[str] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    error_reason: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[str] = None
    vpa: Optional[str] = None
    bank: Optional[str] = None
    wallet: Optional[str] = None
    card_id: Optional[str] = None
    created_at: Optional[int] = None
    captured: Optional[bool] = None

class RazorpayDowntimeEntity(BaseModel):
    id: str
    entity: str = "payment.downtime"
    method: str
    begin: Optional[int] = None
    end: Optional[int] = None
    status: str
    scheduled: bool = False
    severity: Optional[str] = None
    instrument: Optional[dict] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

class WebhookEvent(BaseModel):
    entity: str = "event"
    event: str
    account_id: Optional[str] = None
    contains: list[str] = []
    created_at: Optional[int] = None
    payload: dict[str, Any] = {}