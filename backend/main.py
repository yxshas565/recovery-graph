# backend/main.py
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import json
import logging
from contextlib import asynccontextmanager


from api.episodes     import router as episodes_router
from api.metrics      import router as metrics_router
from api.events_stream import router as events_router
from api.admin        import router as admin_router

import psycopg
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from config import get_settings
from webhook.ingestor import ingest
from episode.state_machine import (
    handle_payment_failed,
    handle_payment_captured,
    handle_payment_authorized,
    expire_provisional_episodes,
)
from webhook.models import RazorpayPaymentEntity

logging.basicConfig(level=logging.INFO)
logger   = logging.getLogger(__name__)
settings = get_settings()

# ── APP STATE ────────────────────────────────────────────────────────────────
pool:  AsyncConnectionPool | None = None
redis: aioredis.Redis | None      = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool, redis

    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        max_size=20,
        open=False,
        kwargs={"autocommit": True, "row_factory": dict_row},
    )

    await pool.open()

    redis = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
    )

    logger.info("DB pool + Redis ready")

    # ── Background expiry worker ─────────────────────────────────────────
    import asyncio

    async def expiry_loop():
        while True:
            try:
                async with pool.connection() as conn:
                    expired = await expire_provisional_episodes(conn)

                    if expired:
                        logger.info(
                            "expired %d episodes to final_failed",
                            len(expired),
                        )

            except asyncio.CancelledError:
                logger.info("expiry loop cancelled")
                raise

            except Exception as e:
                logger.error(
                    "expiry loop error: %s",
                    e,
                    exc_info=True,
                )

            await asyncio.sleep(30)

    expiry_task = asyncio.create_task(expiry_loop())

    try:
        yield
    finally:
        # Stop background worker cleanly
        expiry_task.cancel()

        try:
            await expiry_task
        except asyncio.CancelledError:
            pass

        await pool.close()
        await redis.aclose()

        logger.info("DB pool + Redis closed")

app = FastAPI(title="Recovery Graph", lifespan=lifespan)

app.include_router(episodes_router)
app.include_router(metrics_router)
app.include_router(events_router)
app.include_router(admin_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── HEALTH ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}

# ── WEBHOOK INGESTOR ─────────────────────────────────────────────────────────
@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    async with pool.connection() as conn:
        result = await ingest(request, redis, conn)

    # Dispatch to state machine based on event type
    if result["status"] == "ok":
        event_type = result.get("event")
        payment_id = result.get("payment_id")

        if payment_id:
            raw = await request.body()
            payload = json.loads(raw)

            try:
                pay_entity = payload["payload"]["payment"]["entity"]
                payment    = RazorpayPaymentEntity(**pay_entity)
            except (KeyError, TypeError):
                payment = None

            if payment:
                async with pool.connection() as conn:
                    if event_type == "payment.failed":
                        await handle_payment_failed(
                            conn,
                            payment_id=payment.id,
                            amount_paise=payment.amount,
                            method=payment.method,
                            order_id=payment.order_id,
                            contact=payment.contact,
                            email=payment.email,
                            error_code=payment.error_code,
                            error_description=payment.error_description,
                            error_source=payment.error_source,
                            error_step=payment.error_step,
                            error_reason=payment.error_reason,
                        )
                    elif event_type == "payment.captured":
                        await handle_payment_captured(
                            conn,
                            payment_id=payment.id,
                            amount_paise=payment.amount,
                            method=payment.method,
                            order_id=payment.order_id,
                        )
                    elif event_type == "payment.authorized":
                        await handle_payment_authorized(
                            conn,
                            payment_id=payment.id,
                            amount_paise=payment.amount,
                            method=payment.method,
                            order_id=payment.order_id,
                        )

    return {"ok": True}

# ── BACKGROUND: expire provisional episodes ──────────────────────────────────
# @app.on_event("startup")
# async def start_expiry_loop():
#     import asyncio

#     async def loop():
#         while True:
#             try:
#                 async with pool.connection() as conn:
#                     expired = await expire_provisional_episodes(conn)
#                     if expired:
#                         logger.info("expired %d episodes to final_failed", len(expired))
#             except Exception as e:
#                 logger.error("expiry loop error: %s", e)
#             await asyncio.sleep(30)

#     asyncio.create_task(loop())