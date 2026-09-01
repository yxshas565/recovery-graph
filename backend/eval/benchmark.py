# backend/eval/benchmark.py
"""
Full seeded benchmark. Pre-registers the eval spec into the ledger,
runs counterfactual engine, reports all metrics.
Run AFTER pre-registration, BEFORE seeing outcome data.
"""
import json
import os
from datetime import datetime, timezone

from eval.synthetic_data  import generate_dataset, FAILURE_CLASSES
from eval.counterfactual  import t_learner_lift, diff_in_means
from eval.preregister     import preregister, verify_preregistration, compute_spec_hash, EVAL_SPEC_V1
from ledger.audit_ledger  import AuditLedger

def run_benchmark(conninfo: str, verbose: bool = True) -> dict:
    banner = lambda s: print(f"\n{'─'*60}\n  {s}\n{'─'*60}")

    # 1. Pre-register
    banner("STEP 1 · Pre-registering eval spec")
    reg    = preregister(conninfo)
    spec_hash = reg["spec_hash"]
    if verbose:
        print(f"  spec_hash  : {spec_hash}")
        print(f"  ledger_seq : {reg['ledger_seq']}")

    # 2. Generate dataset (blind — same seed as spec)
    banner("STEP 2 · Generating synthetic dataset")
    rows = generate_dataset(
        n=EVAL_SPEC_V1["dataset_n"],
        seed=EVAL_SPEC_V1["dataset_seed"],
    )
    if verbose:
        print(f"  total rows  : {len(rows)}")
        from collections import Counter
        dist = Counter(r["failure_class"] for r in rows)
        for cls, n in dist.most_common():
            print(f"    {cls:28s}: {n:4d} ({n/len(rows)*100:.1f}%)")

    # 3. Run estimators
    banner("STEP 3 · Running estimators")
    t_result  = t_learner_lift(rows, n_bootstrap=EVAL_SPEC_V1["n_bootstrap"],
                                seed=EVAL_SPEC_V1["seed"])
    dim       = diff_in_means(rows)

    if verbose:
        print(f"\n  T-learner (GBT):")
        print(f"    lift_pp      : {t_result.lift_pp:+.2f}pp")
        print(f"    95% CI       : [{t_result.ci_lower:.2f}, {t_result.ci_upper:.2f}]")
        print(f"    incr revenue : ₹{t_result.incremental_rev/100:,.0f}")
        print(f"    n_treated    : {t_result.n_treated}")
        print(f"    n_control    : {t_result.n_control}")
        print(f"\n  Diff-in-means (RCT arm):")
        print(f"    lift_pp      : {dim['lift_pp']:+.2f}pp")
        print(f"\n  HTE by failure class (est vs truth):")
        for cls, v in t_result.by_class.items():
            delta = v["lift_pp"] - v["truth_lift_pp"]
            print(f"    {cls:28s}: est={v['lift_pp']:+.2f}pp  "
                  f"truth={v['truth_lift_pp']:+.2f}pp  "
                  f"Δ={delta:+.2f}pp  n={v['n']}")

    # 4. Verify pre-registration integrity
    banner("STEP 4 · Verifying pre-registration")
    verified = verify_preregistration(conninfo, spec_hash)
    chain_ok = AuditLedger(conninfo).verify().ok
    if verbose:
        print(f"  spec hash verified : {verified}")
        print(f"  ledger chain ok    : {chain_ok}")

    # 5. Log result to ledger
    result_payload = {
        "spec_hash":            spec_hash,
        "t_learner_lift_pp":    t_result.lift_pp,
        "t_learner_ci":         [t_result.ci_lower, t_result.ci_upper],
        "dim_lift_pp":          dim["lift_pp"],
        "incremental_rev_paise": t_result.incremental_rev,
        "n_treated":            t_result.n_treated,
        "n_control":            t_result.n_control,
        "by_class":             t_result.by_class,
        "chain_ok":             chain_ok,
        "spec_verified":        verified,
        "run_at":               datetime.now(timezone.utc).isoformat(),
    }

    ledger = AuditLedger(conninfo)
    entry  = ledger.append(
        episode_id="eval_result",
        event_type="eval.result",
        payload=result_payload,
    )

    if verbose:
        banner("BENCHMARK COMPLETE")
        print(f"  Result ledger_seq : {entry.entry_seq}")
        print(f"  Result entry_hash : {entry.entry_hash}")
        print(f"\n  ✓ Pre-registered → executed → logged")
        print(f"  ✓ Anyone can verify: sha256(spec) == {spec_hash[:16]}…")
        print(f"  ✓ Ledger chain integrity: {chain_ok}")

    return result_payload

if __name__ == "__main__":
    conninfo = os.environ["DATABASE_URL"]
    run_benchmark(conninfo, verbose=True)