# backend/webhook/ingestor.py
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import psycopg
import redis.asyncio as aioredis
from fastapi import HTTPException, Request
from psycopg.rows import dict_row

from config import get_settings
from webhook.models import WebhookEvent, RazorpayPaymentEntity, RazorpayDowntimeEntity

logger = logging.getLogger(__name__)
settings = get_settings()

# ── SIGNATURE VERIFICATION ───────────────────────────────────────────────────
def verify_signature(raw_body: bytes, signature: str) -> None:
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

# ── REDIS DEDUP ──────────────────────────────────────────────────────────────
async def is_duplicate(redis: aioredis.Redis, event_id: str) -> bool:
    key = f"wh:{event_id}"
    result = await redis.set(key, "1", nx=True, ex=259200)  # 3 days TTL
    return result is None  # None = key already existed = duplicate

# ── PERSIST RAW EVENT ────────────────────────────────────────────────────────
async def persist_event(
    conn: psycopg.AsyncConnection,
    event_id: str,
    event_type: str,
    payment_id: str | None,
    order_id: str | None,
    subscription_id: str | None,
    raw_payload: dict,
) -> None:
    await conn.execute(
        """
        INSERT INTO webhook_events
            (id, event_type, payment_id, order_id, subscription_id, raw_payload)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (id) DO NOTHING
        """,
        (event_id, event_type, payment_id, order_id, subscription_id,
         json.dumps(raw_payload)),
    )

# ── EXTRACT PAYMENT ENTITY ───────────────────────────────────────────────────
def extract_payment(payload: dict) -> RazorpayPaymentEntity | None:
    try:
        entity = payload["payload"]["payment"]["entity"]
        return RazorpayPaymentEntity(**entity)
    except (KeyError, TypeError):
        return None

# ── EXTRACT DOWNTIME ENTITY ──────────────────────────────────────────────────
def extract_downtime(payload: dict) -> RazorpayDowntimeEntity | None:
    try:
        entity = payload["payload"]["payment.downtime"]["entity"]
        return RazorpayDowntimeEntity(**entity)
    except (KeyError, TypeError):
        return None

# ── PERSIST DOWNTIME ─────────────────────────────────────────────────────────
async def persist_downtime(
    conn: psycopg.AsyncConnection,
    dt: RazorpayDowntimeEntity,
    raw_payload: dict,
) -> None:
    await conn.execute(
        """
        INSERT INTO downtime_events
            (id, method, status, severity, scheduled,
             begin_ts, end_ts, instrument, raw_payload)
        VALUES (%s,%s,%s,%s,%s,
                to_timestamp(%s), to_timestamp(%s), %s::jsonb, %s::jsonb)
        ON CONFLICT (id) DO UPDATE SET
            status     = EXCLUDED.status,
            severity   = EXCLUDED.severity,
            end_ts     = EXCLUDED.end_ts,
            instrument = EXCLUDED.instrument,
            raw_payload= EXCLUDED.raw_payload,
            updated_at = NOW()
        """,
        (
            dt.id, dt.method, dt.status, dt.severity, dt.scheduled,
            dt.begin, dt.end,
            json.dumps(dt.instrument) if dt.instrument else None,
            json.dumps(raw_payload),
        ),
    )

# ── MAIN INGESTOR ────────────────────────────────────────────────────────────
async def ingest(
    request: Request,
    redis: aioredis.Redis,
    db_conn: psycopg.AsyncConnection,
) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    event_id  = request.headers.get("x-razorpay-event-id", "")

    # 1. Verify signature — raw bytes, never re-serialised
    verify_signature(raw_body, signature)

    # 2. Parse
    payload = json.loads(raw_body)
    event   = WebhookEvent(**payload)

    # 3. Deduplicate
    if await is_duplicate(redis, event_id):
        logger.info("duplicate event %s — ack and skip", event_id)
        return {"status": "duplicate", "event_id": event_id}

    # 4. Extract entities
    payment  = extract_payment(payload)
    downtime = extract_downtime(payload) if "downtime" in event.event else None

    payment_id      = payment.id if payment else None
    order_id        = payment.order_id if payment else None
    subscription_id = payload.get("payload", {}).get(
        "subscription", {}).get("entity", {}).get("id")

    # 5. Persist raw event
    await persist_event(
        db_conn, event_id, event.event,
        payment_id, order_id, subscription_id, payload,
    )

    # 6. Persist downtime if applicable
    if downtime:
        await persist_downtime(db_conn, downtime, payload)

    await db_conn.commit()

    logger.info("ingested event=%s pay=%s event_id=%s",
                event.event, payment_id, event_id)

    return {
        "status":     "ok",
        "event":      event.event,
        "event_id":   event_id,
        "payment_id": payment_id,
    }