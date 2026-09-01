# backend/eval/preregister.py
import hashlib
import json
from datetime import datetime, timezone

from ledger.audit_ledger import AuditLedger, canonical_json
from config import get_settings

EVAL_SPEC_V1 = {
    "version":          "v1",
    "primary_metric":   "incremental_recovery_rate_pp",
    "estimand":         "ATE_over_failure_eligible_episodes",
    "estimator":        "t_learner_gbt_bootstrap_ci",
    "exclusions":       ["invalid_vpa"],
    "alpha":            0.05,
    "sidedness":        "two",
    "mde_pp":           2.0,
    "baseline":         "naive_retry_T+1h_T+24h_T+72h",
    "n_bootstrap":      200,
    "seed":             42,
    "dataset_n":        200,
    "dataset_seed":     42,
}

def compute_spec_hash(spec: dict) -> str:
    return hashlib.sha256(
        canonical_json(spec).encode("utf-8")
    ).hexdigest()

def preregister(conninfo: str) -> dict:
    settings = get_settings()
    spec_hash = compute_spec_hash(EVAL_SPEC_V1)
    ledger    = AuditLedger(conninfo)

    entry = ledger.append(
        episode_id="eval_preregistration",
        event_type="eval.preregistered",
        payload={
            "spec_hash":       spec_hash,
            "spec":            EVAL_SPEC_V1,
            "registered_at":  datetime.now(timezone.utc).isoformat(),
        },
    )

    return {
        "spec_hash":  spec_hash,
        "ledger_seq": entry.entry_seq,
        "entry_hash": entry.entry_hash,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }

def verify_preregistration(conninfo: str, spec_hash: str) -> bool:
    ledger = AuditLedger(conninfo)
    report = ledger.verify()
    if not report.ok:
        return False
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(conninfo, row_factory=dict_row) as conn:
        rows = conn.execute(
            """SELECT payload_canon FROM ledger_entries
               WHERE event_type = 'eval.preregistered'
               ORDER BY entry_seq""",
        ).fetchall()
    for row in rows:
        payload = json.loads(row["payload_canon"])
        if payload.get("spec_hash") == spec_hash:
            stored = compute_spec_hash(payload["spec"])
            return stored == spec_hash
    return False

if __name__ == "__main__":
    import os
    conninfo = os.environ["DATABASE_URL"]
    result   = preregister(conninfo)
    print("Pre-registered eval spec:")
    print(f"  spec_hash:  {result['spec_hash']}")
    print(f"  ledger_seq: {result['ledger_seq']}")
    print(f"  entry_hash: {result['entry_hash']}")
    ok = verify_preregistration(conninfo, result['spec_hash'])
    print(f"  verified:   {ok}")