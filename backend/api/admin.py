# backend/api/admin.py
import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from config import get_settings

router   = APIRouter(prefix="/api/admin", tags=["admin"])
settings = get_settings()

def require_admin(x_admin_secret: str = Header(...)):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(403, "forbidden")

class InjectRequest(BaseModel):
    scenario: str
    payment_id: str | None = None
    amount_paise: int = 50000

def build_scenario(req: InjectRequest) -> list[dict]:
    pid    = req.payment_id or f"pay_{uuid.uuid4().hex[:14]}"
    amount = req.amount_paise
    now    = int(datetime.now(timezone.utc).timestamp())

    base_payment = {
        "id": pid, "entity": "payment",
        "amount": amount, "currency": "INR",
        "created_at": now,
    }

    scenarios = {
        # The key scenario — documented Razorpay UPI retry sequence
        "upi_late_capture": [
            {"delay_s": 0, "body": {
                "event": "payment.failed",
                "payload": {"payment": {"entity": {
                    **base_payment, "status": "failed",
                    "method": "upi", "vpa": "test@upi",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Payment failed",
                    "error_source": "customer",
                    "error_step": "payment_authentication",
                    "error_reason": "payment_cancelled",
                }}},
            }},
            {"delay_s": 3, "body": {
                "event": "payment.captured",
                "payload": {"payment": {"entity": {
                    **base_payment, "status": "captured",
                    "method": "upi", "captured": True,
                }}},
            }},
        ],
        "card_final_failure": [
            {"delay_s": 0, "body": {
                "event": "payment.failed",
                "payload": {"payment": {"entity": {
                    **base_payment, "status": "failed",
                    "method": "card",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Card expired",
                    "error_source": "issuer",
                    "error_step": "payment_authorization",
                    "error_reason": "expired_card",
                }}},
            }},
        ],
        "insufficient_funds": [
            {"delay_s": 0, "body": {
                "event": "payment.failed",
                "payload": {"payment": {"entity": {
                    **base_payment, "status": "failed",
                    "method": "upi",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "insufficient balance in account",
                    "error_source": "customer",
                    "error_step": "payment_authorization",
                    "error_reason": "insufficient_funds",
                }}},
            }},
        ],
        "duplicate_event": [
            {"delay_s": 0, "event_id": "evt_dedup_test_001", "body": {
                "event": "payment.failed",
                "payload": {"payment": {"entity": {
                    **base_payment, "status": "failed",
                    "method": "upi",
                    "error_description": "Payment failed",
                }}},
            }},
            {"delay_s": 1, "event_id": "evt_dedup_test_001", "body": {
                "event": "payment.failed",
                "payload": {"payment": {"entity": {
                    **base_payment, "status": "failed",
                    "method": "upi",
                    "error_description": "Payment failed",
                }}},
            }},
        ],
        "invalid_vpa": [
            {"delay_s": 0, "body": {
                "event": "payment.failed",
                "payload": {"payment": {"entity": {
                    **base_payment, "status": "failed",
                    "method": "upi", "vpa": "invalid@xyz",
                    "error_description": "invalid VPA provided",
                    "error_reason": "invalid_vpa",
                }}},
            }},
        ],
    }

    return scenarios.get(req.scenario, scenarios["card_final_failure"])

@router.post("/inject")
async def inject_scenario(
    req: InjectRequest,
    _: None = Depends(require_admin),
):
    if settings.environment == "production":
        raise HTTPException(403, "injection disabled in production")

    payloads = build_scenario(req)
    notes = []

    from main import app

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
    ) as client:
        for p in payloads:
            body = json.dumps(
                p["body"],
                separators=(",", ":"),
            ).encode()

            sig = hmac.new(
                settings.razorpay_webhook_secret.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()

            event_id = (
                p.get("event_id")
                or f"evt_{uuid.uuid4().hex[:20]}"
            )

            r = await client.post(
                "/webhooks/razorpay",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Razorpay-Signature": sig,
                    "x-razorpay-event-id": event_id,
                },
            )

            notes.append(
                f"{p['body']['event']} -> {r.status_code}"
            )

            await asyncio.sleep(
                p.get("delay_s", 0.5)
            )

    return {"injected": notes}

@router.get("/scenarios")
async def list_scenarios(_: None = Depends(require_admin)):
    return {"scenarios": [
        "upi_late_capture",
        "card_final_failure",
        "insufficient_funds",
        "duplicate_event",
        "invalid_vpa",
    ]}