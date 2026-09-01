# backend/api/episodes.py
import json
from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row
import psycopg

from config import get_settings
from ledger.audit_ledger import AuditLedger

router   = APIRouter(prefix="/api/episodes", tags=["episodes"])
settings = get_settings()

@router.get("")
async def list_episodes(limit: int = 50, offset: int = 0):
    async with await psycopg.AsyncConnection.connect(
        settings.database_url, row_factory=dict_row
    ) as conn:
        rows = await conn.execute(
            """SELECT id, payment_id, amount_paise, state,
                      failure_class, attempts, created_at,
                      updated_at, recovery_link_id, intervention_type
               FROM episodes ORDER BY created_at DESC
               LIMIT %s OFFSET %s""",
            (limit, offset),
        )
        return {"episodes": [dict(r) for r in await rows.fetchall()]}

@router.get("/{episode_id}")
async def get_episode(episode_id: str):
    async with await psycopg.AsyncConnection.connect(
        settings.database_url, row_factory=dict_row
    ) as conn:
        row = await (await conn.execute(
            "SELECT * FROM episodes WHERE id = %s", (episode_id,)
        )).fetchone()
        if not row:
            raise HTTPException(404, "episode not found")
        return dict(row)

@router.get("/{episode_id}/actions")
async def get_episode_actions(episode_id: str):
    async with await psycopg.AsyncConnection.connect(
        settings.database_url, row_factory=dict_row
    ) as conn:
        rows = await (await conn.execute(
            """SELECT * FROM episode_actions
               WHERE episode_id = %s ORDER BY created_at""",
            (episode_id,),
        )).fetchall()
        return {"actions": [dict(r) for r in rows]}

@router.get("/{episode_id}/replay")
async def replay_episode(episode_id: str):
    ledger = AuditLedger(settings.database_url)
    try:
        result = ledger.replay_episode(episode_id)
        return {
            "episode_id":  result.episode_id,
            "chain_ok":    result.chain_ok,
            "decisions":   result.decisions,
            "final_state": result.final_state,
            "head_proof":  result.head_proof,
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/{episode_id}/ledger")
async def get_ledger_entries(episode_id: str):
    ledger = AuditLedger(settings.database_url)
    report = ledger.verify()
    async with await psycopg.AsyncConnection.connect(
        settings.database_url, row_factory=dict_row
    ) as conn:
        rows = await (await conn.execute(
            """SELECT entry_seq, event_type, payload_canon,
                      payload_hash, prev_hash, entry_hash, created_at
               FROM ledger_entries
               WHERE chain_id = 'main' AND episode_id = %s
               ORDER BY entry_seq""",
            (episode_id,),
        )).fetchall()

    entries = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d.pop("payload_canon"))
        entries.append(d)

    return {
        "entries":    entries,
        "chain_ok":   report.ok,
        "head":       ledger.head(),
    }