# backend/episode/state_machine.py
import json
import logging
from datetime import datetime, timezone, timedelta

from ledger.audit_ledger import AuditLedger

import psycopg
from psycopg.rows import dict_row

from config import get_settings
from episode.models import EpisodeState, STATE_PRECEDENCE

logger = logging.getLogger(__name__)
settings = get_settings()

# ── STATE PRECEDENCE GUARD ───────────────────────────────────────────────────
def can_transition(current: str, target: str) -> bool:
    cur_p = STATE_PRECEDENCE.get(EpisodeState(current), 0)
    tgt_p = STATE_PRECEDENCE.get(EpisodeState(target), 0)
    return tgt_p > cur_p

# ── GET OR CREATE EPISODE ────────────────────────────────────────────────────
async def get_or_create_episode(
    conn: psycopg.AsyncConnection,
    payment_id: str,
    amount_paise: int,
    currency: str = "INR",
    method: str | None = None,
    order_id: str | None = None,
    contact: str | None = None,
    email: str | None = None,
) -> dict:
    episode_id = f"episode:{payment_id}"
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT * FROM episodes WHERE id = %s", (episode_id,)
        )
        row = await cur.fetchone()
        if row:
            return dict(row)

        await cur.execute(
            """
            INSERT INTO episodes
                (id, payment_id, order_id, amount_paise, currency,
                 method, contact, email, state)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING *
            """,
            (episode_id, payment_id, order_id, amount_paise, currency,
             method, contact, email, EpisodeState.CREATED),
        )
        row = await cur.fetchone()
        await conn.commit()
        logger.info("created episode %s", episode_id)
        return dict(row)

# ── TRANSITION STATE ─────────────────────────────────────────────────────────
async def transition(
    conn: psycopg.AsyncConnection,
    episode_id: str,
    target_state: EpisodeState,
    extra_updates: dict | None = None,
) -> dict | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT id, state, attempts FROM episodes WHERE id = %s FOR UPDATE",
            (episode_id,),
        )
        row = await cur.fetchone()
        if not row:
            logger.error("episode %s not found", episode_id)
            return None

        current_state = row["state"]
        if not can_transition(current_state, target_state):
            logger.warning(
                "blocked transition %s → %s for %s (precedence rule)",
                current_state, target_state, episode_id,
            )
            return None

        updates = {"state": target_state, "updated_at": datetime.now(timezone.utc)}
        if extra_updates:
            updates.update(extra_updates)

        # Set wait window for provisional_failed
        if target_state == EpisodeState.PROVISIONAL_FAILED:
            updates["wait_until"] = datetime.now(timezone.utc) + timedelta(
                seconds=settings.provisional_wait_seconds
            )

        # Set final_at for terminal states
        if target_state in (
            EpisodeState.RECOVERED,
            EpisodeState.FINAL_FAILED,
            EpisodeState.CAPTURED_LATE,
            EpisodeState.ESCALATED,
        ):
            updates["final_at"] = datetime.now(timezone.utc)

        set_clause = ", ".join(f"{k} = %s" for k in updates)
        await cur.execute(
            f"UPDATE episodes SET {set_clause} WHERE id = %s RETURNING *",
            (*updates.values(), episode_id),
        )
        updated = await cur.fetchone()
        await conn.commit()
        logger.info(
            "episode %s transitioned %s → %s",
            episode_id, current_state, target_state,
        )
        return dict(updated)

# ── HANDLE payment.failed ────────────────────────────────────────────────────
async def handle_payment_failed(
    conn: psycopg.AsyncConnection,
    payment_id: str,
    amount_paise: int,
    method: str | None,
    order_id: str | None,
    contact: str | None,
    email: str | None,
    error_code: str | None,
    error_description: str | None,
    error_source: str | None,
    error_step: str | None,
    error_reason: str | None,
) -> dict:
    episode = await get_or_create_episode(
        conn, payment_id, amount_paise, "INR",
        method, order_id, contact, email,
    )
    episode_id = episode["id"]

    # Already captured — stale out-of-order failed event, ignore
    if episode["state"] in (
        EpisodeState.CAPTURED_LATE,
        EpisodeState.RECOVERED,
    ):
        logger.info(
            "ignoring stale payment.failed for already-captured episode %s",
            episode_id,
        )
        return {"action": "ignored_stale_failed", "episode": episode}

    updated = await transition(conn, episode_id, EpisodeState.PROVISIONAL_FAILED)

    # # Run the autonomous recovery graph only after the provisional
    # # failure has been recorded. Import locally to avoid circular imports.
    # from agents.graph import recovery_graph

    # ledger = AuditLedger(settings.database_url)

    # graph_state = {
    #     "episode_id": episode_id,
    #     "payment_id": payment_id,
    #     "amount_paise": amount_paise,
    #     "method": method,
    #     "error_code": error_code,
    #     "error_description": error_description,
    #     "error_source": error_source,
    #     "error_step": error_step,
    #     "error_reason": error_reason,
    #     "has_active_downtime": False,
    #     "events": [],
    # }

    # graph_config = {
    #     "configurable": {
    #         "conn": conn,
    #         "conninfo": settings.database_url,
    #         "episode": updated or episode,
    #         "ledger": ledger,
    #     }
    # }

    # try:
    #     graph_result = await recovery_graph.ainvoke(
    #         graph_state,
    #         config=graph_config,
    #     )
    # except Exception:
    #     logger.exception(
    #         "recovery graph failed for episode %s",
    #         episode_id,
    #     )
    #     raise


    # IMPORTANT:
    # Do NOT run the recovery graph immediately.
    #
    # A payment.failed event is provisional. The payment may still
    # legitimately become captured shortly afterwards. The expiry
    # loop is responsible for starting recovery only after the
    # provisional window has elapsed.
    logger.info(
        "episode %s is provisional_failed; recovery graph deferred until "
        "provisional window expires",
        episode_id,
    )

    graph_result = None

    return {
        "action": "provisional_failed",
        "episode": updated or episode,
        "graph": graph_result,
        "error": {
            "code": error_code,
            "description": error_description,
            "source": error_source,
            "step": error_step,
            "reason": error_reason,
        },
    }

# ── HANDLE payment.captured ──────────────────────────────────────────────────
async def handle_payment_captured(
    conn: psycopg.AsyncConnection,
    payment_id: str,
    amount_paise: int,
    method: str | None,
    order_id: str | None,
) -> dict:
    episode = await get_or_create_episode(
        conn, payment_id, amount_paise, "INR", method, order_id,
    )
    episode_id = episode["id"]
    current    = episode["state"]

    # Previously failed — this is the documented UPI late-capture sequence
    if current == EpisodeState.PROVISIONAL_FAILED:
        updated = await transition(
            conn, episode_id, EpisodeState.CAPTURED_LATE
        )
        return {"action": "captured_late", "episode": updated}

    # Recovery link was paid
    if current == EpisodeState.RETRY_PENDING:
        updated = await transition(
            conn, episode_id, EpisodeState.RECOVERED
        )
        return {"action": "recovered", "episode": updated}

    # Normal first capture
    updated = await transition(conn, episode_id, EpisodeState.CAPTURED_LATE)
    return {"action": "captured", "episode": updated}

# ── HANDLE payment.authorized ────────────────────────────────────────────────
async def handle_payment_authorized(
    conn: psycopg.AsyncConnection,
    payment_id: str,
    amount_paise: int,
    method: str | None,
    order_id: str | None,
) -> dict:
    # Late-auth case — bank responded after timeout
    episode = await get_or_create_episode(
        conn, payment_id, amount_paise, "INR", method, order_id,
    )
    return {"action": "late_authorized", "episode": episode,
            "note": "capture manually via POST /v1/payments/:id/capture"}

# ── CHECK WAIT WINDOWS (called by background task) ───────────────────────────
# async def expire_provisional_episodes(
#     conn: psycopg.AsyncConnection,
# ) -> list[str]:
#     now = datetime.now(timezone.utc)
#     async with conn.cursor(row_factory=dict_row) as cur:
#         await cur.execute(
#             """
#             SELECT id FROM episodes
#             WHERE state = %s AND wait_until < %s
#             """,
#             (EpisodeState.PROVISIONAL_FAILED, now),
#         )
#         rows = await cur.fetchall()

#     expired = []
#     for row in rows:
#         updated = await transition(
#             conn, row["id"], EpisodeState.FINAL_FAILED
#         )
#         if updated:
#             expired.append(row["id"])
#             logger.info("episode %s expired to final_failed", row["id"])

#             # Run the autonomous recovery graph after final failure.
#             try:
#                 from agents.graph import recovery_graph
#                 from ledger.audit_ledger import AuditLedger

#                 # Reload the complete episode after the transition.
#                 async with conn.cursor(row_factory=dict_row) as cur:
#                     await cur.execute(
#                         "SELECT * FROM episodes WHERE id = %s",
#                         (row["id"],),
#                     )
#                     final_episode = await cur.fetchone()

#                 if final_episode:
#                     ledger = AuditLedger(settings.database_url)

#                     initial_state = {
#                         "episode_id": final_episode["id"],
#                         "payment_id": final_episode["payment_id"],
#                         "amount_paise": final_episode["amount_paise"],
#                         "method": final_episode.get("method"),
#                         "error_code": None,
#                         "error_description": None,
#                         "error_source": None,
#                         "error_step": None,
#                         "error_reason": None,
#                         "has_active_downtime": False,
#                         "events": [],
#                     }

#                     result = await recovery_graph.ainvoke(
#                         initial_state,
#                         config={
#                             "configurable": {
#                                 "conn": conn,
#                                 "conninfo": settings.database_url,
#                                 "episode": final_episode,
#                                 "ledger": ledger,
#                             }
#                         },
#                     )

#                     logger.info(
#                         "recovery graph completed for %s: %s",
#                         row["id"],
#                         result.get("result"),
#                     )

#             except Exception:
#                 logger.exception(
#                     "recovery graph failed for episode %s",
#                     row["id"],
#                 )

#     return expired




async def expire_provisional_episodes(
    conn: psycopg.AsyncConnection,
) -> list[str]:
    now = datetime.now(timezone.utc)

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT id
            FROM episodes
            WHERE state = %s
              AND wait_until < %s
            """,
            (EpisodeState.PROVISIONAL_FAILED, now),
        )
        rows = await cur.fetchall()

    expired = []

    for row in rows:
        episode_id = row["id"]

        updated = await transition(
            conn,
            episode_id,
            EpisodeState.FINAL_FAILED,
        )

        if not updated:
            continue

        expired.append(episode_id)

        logger.info(
            "episode %s expired to final_failed",
            episode_id,
        )

        # ── Run autonomous recovery graph ─────────────────────────────
        try:
            # Local imports avoid the state_machine ↔ executor circular import.
            from agents.graph import recovery_graph
            from ledger.audit_ledger import AuditLedger

            # Reload the complete episode after FINAL_FAILED transition.
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM episodes WHERE id = %s",
                    (episode_id,),
                )
                episode = await cur.fetchone()

            if not episode:
                logger.error(
                    "episode %s disappeared before recovery graph",
                    episode_id,
                )
                continue

            # Retrieve the original payment.failed webhook.
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT raw_payload
                    FROM webhook_events
                    WHERE payment_id = %s
                      AND event_type = 'payment.failed'
                    ORDER BY received_at DESC
                    LIMIT 1
                    """,
                    (episode["payment_id"],),
                )
                webhook = await cur.fetchone()

            payload = webhook["raw_payload"] if webhook else {}

            entity = (
                payload
                .get("payload", {})
                .get("payment", {})
                .get("entity", {})
            )

            # Check for active downtime for this payment method.
            has_active_downtime = False

            if episode.get("method"):
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT 1
                        FROM downtime_events
                        WHERE method = %s
                          AND status = 'resolved'
                        LIMIT 1
                        """,
                        (episode["method"],),
                    )
                    has_active_downtime = await cur.fetchone() is not None

            ledger = AuditLedger(settings.database_url)

            agent_state = {
                "episode_id": episode["id"],
                "payment_id": episode["payment_id"],
                "amount_paise": episode["amount_paise"],
                "method": episode.get("method"),
                "error_code": entity.get("error_code"),
                "error_description": entity.get("error_description"),
                "error_source": entity.get("error_source"),
                "error_step": entity.get("error_step"),
                "error_reason": entity.get("error_reason"),
                "has_active_downtime": has_active_downtime,
                "events": [],
            }

            result = await recovery_graph.ainvoke(
                agent_state,
                config={
                    "configurable": {
                        "conn": conn,
                        "conninfo": settings.database_url,
                        "episode": episode,
                        "ledger": ledger,
                    }
                },
            )

            logger.info(
                "recovery graph completed for %s: result=%s",
                episode_id,
                result.get("result"),
            )

        except Exception:
            logger.exception(
                "recovery graph failed for episode %s",
                episode_id,
            )

    return expired
