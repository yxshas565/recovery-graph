# backend/agents/executor.py
import json
import logging
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from config import get_settings
from episode.models import EpisodeState, PolicyRuling
from episode.state_machine import transition
# from rzp_client.payment_links import create_recovery_link
from rzp_client.payment_links import create_recovery_link
from ledger.audit_ledger import AuditLedger

logger   = logging.getLogger(__name__)
settings = get_settings()

async def execute_recovery(
    conn: psycopg.AsyncConnection,
    episode: dict,
    ruling: PolicyRuling,
    diagnosis_payload: dict,
    ledger: AuditLedger,
) -> dict:
    episode_id = episode["id"]
    offer      = ruling.selected_offer

    if not ruling.approved or not offer:
        # Escalate
        await transition(conn, episode_id, EpisodeState.ESCALATED)
        ledger.append(episode_id, "episode.escalated", {
            "episode_id":       episode_id,
            "rejection_reason": ruling.rejection_reason,
            "rule_violations":  ruling.rule_violations,
        })
        return {"action": "escalated", "reason": ruling.rejection_reason}

    if offer.offer_type == "fresh_link":
        attempt_num = episode.get("attempts", 0) + 1

        # Deterministic code owns the Razorpay call — never LLM
        try:
            link = create_recovery_link(
                episode_id=episode_id,
                amount_paise=offer.amount_paise,
                attempt_num=attempt_num,
                contact=episode.get("contact"),
                email=episode.get("email"),
                description=f"Recovery for payment {episode['payment_id']}",
                expire_in_seconds=offer.expires_in_seconds,
            )
        except Exception as e:
            logger.error("failed to create recovery link: %s", e)
            ledger.append(episode_id, "episode.executor_error", {
                "episode_id": episode_id,
                "error":      str(e),
            })
            raise

        # Update episode — increment attempts, store link id
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE episodes SET
                    attempts         = attempts + 1,
                    recovery_link_id = %s,
                    recovery_ref_id  = %s,
                    recovery_amount  = %s,
                    intervention_type= %s,
                    updated_at       = NOW()
                   WHERE id = %s""",
                (
                    link["id"],
                    link["reference_id"],
                    offer.amount_paise,
                    "fresh_link",
                    episode_id,
                ),
            )
            await conn.commit()

        # Transition to retry_pending
        updated = await transition(conn, episode_id, EpisodeState.RETRY_PENDING)

        # Append to immutable ledger
        ledger.append(episode_id, "episode.recovery_link_created", {
            "episode_id":      episode_id,
            "payment_id":      episode["payment_id"],
            "razorpay_link_id": link["id"],
            "reference_id":    link["reference_id"],
            "amount_paise":    offer.amount_paise,
            "short_url":       link.get("short_url"),
            "expires_in_s":    offer.expires_in_seconds,
            "offer_rationale": offer.rationale,
            "diagnosis":       diagnosis_payload,
            "attempt_num":     attempt_num,
        })

        logger.info(
            "recovery link created ep=%s link=%s url=%s",
            episode_id, link["id"], link.get("short_url"),
        )

        return {
            "action":     "recovery_link_created",
            "link_id":    link["id"],
            "short_url":  link.get("short_url"),
            "amount":     offer.amount_paise,
            "episode":    updated,
        }

    return {"action": "no_op", "reason": "unhandled_offer_type"}
