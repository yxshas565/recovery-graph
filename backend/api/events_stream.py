# backend/api/events_stream.py
import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import psycopg
from psycopg.rows import dict_row
from config import get_settings

router   = APIRouter(prefix="/api/events", tags=["events"])
settings = get_settings()

@router.get("/stream")
async def event_stream(request: Request, after: str | None = None):
    async def gen():
        last_id = int(after) if after else 0
        while not await request.is_disconnected():
            try:
                async with await psycopg.AsyncConnection.connect(
                    settings.database_url, row_factory=dict_row
                ) as conn:
                    rows = await (await conn.execute(
                        """SELECT e.id, e.payment_id, e.state,
                                  e.failure_class, e.amount_paise,
                                  e.updated_at,
                                  ea.id AS action_id,
                                  ea.action_type, ea.created_at AS action_at
                           FROM episodes e
                           LEFT JOIN episode_actions ea ON ea.episode_id = e.id
                           WHERE ea.id > %s OR (ea.id IS NULL AND e.id > %s)
                           ORDER BY COALESCE(ea.id, 0) DESC
                           LIMIT 20""",
                        (last_id, last_id),
                    )).fetchall()

                for row in reversed(rows):
                    d = dict(row)
                    eid = d.get("action_id") or 0
                    if eid > last_id:
                        last_id = eid
                    payload = json.dumps(d, default=str)
                    yield f"id: {eid}\nevent: episode_update\ndata: {payload}\n\n"

                if not rows:
                    yield ": hb\n\n"

            except Exception:
                yield ": hb\n\n"

            await asyncio.sleep(2)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )