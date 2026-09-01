# backend/episode/manager.py
import logging
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from config import get_settings
from agents.graph import recovery_graph
from ledger.audit_ledger import AuditLedger

logger   = logging.getLogger(__name__)
settings = get_settings()

async def trigger_recovery_agent(
    pool: AsyncConnectionPool,
    episode_id: str,
    payment_id: str,
    amount_paise: int,
    method: str | None,
    error_code: str | None,
    error_description: str | None,
    error_source: str | None,
    error_step: str | None,
    error_reason: str | None,
    has_active_downtime: bool = False,
) -> dict:
    ledger = AuditLedger(settings.database_url)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM episodes WHERE id = %s", (episode_id,)
            )
            episode = await cur.fetchone()

    if not episode:
        logger.error("episode %s not found for agent trigger", episode_id)
        return {"error": "episode_not_found"}

    config = {
        "configurable": {
            "conninfo":  settings.database_url,
            "episode":   dict(episode),
            "conn":      None,
            "ledger":    ledger,
        }
    }

    initial_state = {
        "episode_id":          episode_id,
        "payment_id":          payment_id,
        "amount_paise":        amount_paise,
        "method":              method,
        "error_code":          error_code,
        "error_description":   error_description,
        "error_source":        error_source,
        "error_step":          error_step,
        "error_reason":        error_reason,
        "has_active_downtime": has_active_downtime,
        "events":              [],
    }

    try:
        async with pool.connection() as conn:
            config["configurable"]["conn"] = conn
            result = await recovery_graph.ainvoke(initial_state, config)
            logger.info("agent completed for %s: %s",
                        episode_id, result.get("result", {}).get("action"))
            return result
    except Exception as e:
        logger.error("agent error for %s: %s", episode_id, e)
        ledger.append(episode_id, "episode.agent_error", {
            "episode_id": episode_id, "error": str(e),
        })
        raise