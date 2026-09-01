# backend/api/metrics.py
from fastapi import APIRouter
import psycopg
from psycopg.rows import dict_row
from config import get_settings

router   = APIRouter(prefix="/api/metrics", tags=["metrics"])
settings = get_settings()

@router.get("")
async def get_metrics():
    async with await psycopg.AsyncConnection.connect(
        settings.database_url, row_factory=dict_row
    ) as conn:
        summary = await (await conn.execute(
            """SELECT
                COUNT(*)                                        AS total,
                COUNT(*) FILTER (WHERE state='recovered')      AS recovered,
                COUNT(*) FILTER (WHERE state='final_failed')   AS final_failed,
                COUNT(*) FILTER (WHERE state='captured_late')  AS captured_late,
                COUNT(*) FILTER (WHERE state='escalated')      AS escalated,
                COUNT(*) FILTER (WHERE state='retry_pending')  AS retry_pending,
                ROUND(
                  100.0 * COUNT(*) FILTER (WHERE state='recovered')
                  / NULLIF(COUNT(*) FILTER (WHERE state IN
                    ('recovered','final_failed','escalated')), 0), 2
                )                                              AS recovery_rate_pct,
                AVG(
                  EXTRACT(EPOCH FROM (final_at - created_at))/60
                ) FILTER (WHERE state='recovered')             AS avg_recovery_min
               FROM episodes"""
        )).fetchone()

        by_class = await (await conn.execute(
            """SELECT failure_class,
                      COUNT(*) AS total,
                      COUNT(*) FILTER (WHERE state='recovered') AS recovered
               FROM episodes
               WHERE failure_class IS NOT NULL
               GROUP BY failure_class ORDER BY total DESC"""
        )).fetchall()

        dup_prevented = await (await conn.execute(
            """SELECT COUNT(*) AS n FROM webhook_events
               WHERE processed = FALSE
               AND event_type IN ('payment.captured','payment.authorized')"""
        )).fetchone()

    return {
        "summary":           dict(summary) if summary else {},
        "by_failure_class":  [dict(r) for r in by_class],
        "duplicate_prevented": dup_prevented["n"] if dup_prevented else 0,
    }