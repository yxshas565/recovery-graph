import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_settings
from api.admin import InjectRequest, build_scenario

router = APIRouter(prefix="/api/demo", tags=["demo"])
settings = get_settings()

ALLOWED_SCENARIOS = {
    "upi_late_capture",
    "card_final_failure",
    "insufficient_funds",
    "duplicate_event",
    "invalid_vpa",
}

_demo_lock = asyncio.Lock()


class DemoInjectRequest(BaseModel):
    scenario: str
    amount_paise: int = 50000


@router.post("/inject")
async def inject_demo(req: DemoInjectRequest):
    if req.scenario not in ALLOWED_SCENARIOS:
        raise HTTPException(400, "Unknown demo scenario")

    if req.amount_paise < 100 or req.amount_paise > 10000000:
        raise HTTPException(400, "Demo amount must be between 100 and 10000000 paise")

    async with _demo_lock:
        scenario_req = InjectRequest(scenario=req.scenario, amount_paise=req.amount_paise)
        payloads = build_scenario(scenario_req)

        from main import app

        transport = httpx.ASGITransport(app=app)

        notes = []

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
                    or f"evt_demo_{uuid.uuid4().hex[:20]}"
                )

                response = await client.post(
                    "/webhooks/razorpay",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Razorpay-Signature": sig,
                        "x-razorpay-event-id": event_id,
                    },
                )

                notes.append(
                    f"{p['body']['event']} -> {response.status_code}: {response.text}"
                )

                await asyncio.sleep(p.get("delay_s", 0.5))

        return {
            "demo": True,
            "scenario": req.scenario,
            "injected": notes,
        }
