# backend/ledger/audit_ledger.py
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Callable

import psycopg
from psycopg.rows import dict_row

GENESIS_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_payload_hash(payload_canon: str) -> str:
    return sha256_hex(payload_canon.encode("utf-8"))


def compute_entry_hash(chain_id: str, entry_seq: int, episode_id: str,
                       event_type: str, payload_hash: str, prev_hash: str) -> str:
    envelope = {
        "chain_id":    chain_id,
        "entry_seq":   entry_seq,
        "episode_id":  episode_id,
        "event_type":  event_type,
        "payload_hash": payload_hash,
        "prev_hash":   prev_hash,
    }
    return sha256_hex(canonical_json(envelope).encode("utf-8"))


@dataclass(frozen=True)
class LedgerEntry:
    chain_id:     str
    entry_seq:    int
    episode_id:   str
    event_type:   str
    payload:      dict
    payload_canon: str
    payload_hash: str
    prev_hash:    str
    entry_hash:   str


@dataclass(frozen=True)
class ChainFault:
    seq:    int | None
    kind:   str
    detail: str


@dataclass(frozen=True)
class VerifyReport:
    ok:              bool
    entries_checked: int
    head_seq:        int
    head_hash:       str
    faults:          tuple[ChainFault, ...]


@dataclass
class ReplayResult:
    episode_id:  str
    final_state: dict
    decisions:   list[dict]
    chain_ok:    bool
    head_proof:  dict


class AuditLedger:
    def __init__(self, conninfo: str, chain_id: str = "main"):
        self.conninfo = conninfo
        self.chain_id = chain_id

    def append(self, episode_id: str, event_type: str, payload: dict) -> LedgerEntry:
        canon = canonical_json(payload)
        ph    = compute_payload_hash(canon)

        with psycopg.connect(self.conninfo, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO ledger_head (chain_id) VALUES (%s) "
                    "ON CONFLICT (chain_id) DO NOTHING",
                    (self.chain_id,),
                )
                cur.execute(
                    "UPDATE ledger_head SET last_seq = last_seq + 1 "
                    "WHERE chain_id = %s RETURNING last_seq, last_hash",
                    (self.chain_id,),
                )
                head      = cur.fetchone()
                seq, prev = head["last_seq"], head["last_hash"]
                eh        = compute_entry_hash(
                    self.chain_id, seq, episode_id, event_type, ph, prev
                )
                cur.execute(
                    """
                    INSERT INTO ledger_entries
                        (chain_id, entry_seq, episode_id, event_type,
                         payload, payload_canon, payload_hash, prev_hash, entry_hash)
                    VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                    """,
                    (self.chain_id, seq, episode_id, event_type,
                     canon, canon, ph, prev, eh),
                )
                cur.execute(
                    "UPDATE ledger_head SET last_hash = %s WHERE chain_id = %s",
                    (eh, self.chain_id),
                )
            conn.commit()

        return LedgerEntry(self.chain_id, seq, episode_id, event_type,
                           json.loads(canon), canon, ph, prev, eh)

    def verify(self, start_seq: int = 1, end_seq: int | None = None,
               anchor_hash: str = GENESIS_HASH) -> VerifyReport:
        faults: list[ChainFault] = []
        prev_hash, expected_seq, checked = anchor_hash, start_seq, 0

        with psycopg.connect(self.conninfo, row_factory=dict_row) as conn:
            with conn.cursor(name="ledger_verify") as cur:
                cur.itersize = 5000
                cur.execute(
                    "SELECT entry_seq, episode_id, event_type, payload_canon, "
                    "payload_hash, prev_hash, entry_hash "
                    "FROM ledger_entries WHERE chain_id = %s AND entry_seq >= %s "
                    + ("AND entry_seq <= %s " if end_seq else "")
                    + "ORDER BY entry_seq",
                    (self.chain_id, start_seq, end_seq)
                    if end_seq else (self.chain_id, start_seq),
                )
                for row in cur:
                    seq = row["entry_seq"]
                    if seq != expected_seq:
                        faults.append(ChainFault(seq, "SEQ_GAP",
                            f"expected {expected_seq}, found {seq}"))
                    if row["prev_hash"] != prev_hash:
                        faults.append(ChainFault(seq, "BROKEN_LINK",
                            f"prev_hash != hash of seq {expected_seq - 1}"))
                    if row["payload_hash"] != compute_payload_hash(row["payload_canon"]):
                        faults.append(ChainFault(seq, "PAYLOAD_TAMPERED",
                            "payload_hash mismatch"))
                    recomputed = compute_entry_hash(
                        self.chain_id, seq, row["episode_id"],
                        row["event_type"], row["payload_hash"], row["prev_hash"],
                    )
                    if row["entry_hash"] != recomputed:
                        faults.append(ChainFault(seq, "HASH_TAMPERED",
                            "entry_hash does not recompute"))
                    prev_hash, expected_seq, checked = (
                        row["entry_hash"], seq + 1, checked + 1
                    )

        return VerifyReport(
            ok=not faults, entries_checked=checked,
            head_seq=expected_seq - 1, head_hash=prev_hash,
            faults=tuple(faults),
        )

    def head(self) -> dict:
        with psycopg.connect(self.conninfo, row_factory=dict_row) as conn:
            row = conn.execute(
                "SELECT last_seq, last_hash FROM ledger_head WHERE chain_id = %s",
                (self.chain_id,),
            ).fetchone()
        return {
            "chain_id":  self.chain_id,
            "head_seq":  row["last_seq"]  if row else 0,
            "head_hash": row["last_hash"] if row else GENESIS_HASH,
        }

    def replay_episode(
        self,
        episode_id: str,
        reducers: dict[str, Callable[[dict, dict], dict]] | None = None,
        verify_first: bool = True,
    ) -> ReplayResult:
        report  = self.verify() if verify_first else None
        faulted = {f.seq for f in report.faults} if report else set()

        decisions: list[dict] = []
        state:     dict       = {}

        with psycopg.connect(self.conninfo, row_factory=dict_row) as conn:
            rows = conn.execute(
                "SELECT entry_seq, event_type, payload_canon FROM ledger_entries "
                "WHERE chain_id = %s AND episode_id = %s ORDER BY entry_seq",
                (self.chain_id, episode_id),
            ).fetchall()

        for row in rows:
            if row["entry_seq"] in faulted:
                raise ValueError(
                    f"replay aborted: ledger fault at seq {row['entry_seq']}"
                )
            payload = json.loads(row["payload_canon"])
            decisions.append({
                "seq":        row["entry_seq"],
                "event_type": row["event_type"],
                "payload":    payload,
            })
            fn    = (reducers or {}).get(
                row["event_type"],
                lambda s, p: {**s, "last_event": p},
            )
            state = fn(state, payload)

        return ReplayResult(
            episode_id=episode_id,
            final_state=state,
            decisions=decisions,
            chain_ok=(report.ok if report else False),
            head_proof=self.head(),
        )
