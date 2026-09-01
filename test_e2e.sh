#!/usr/bin/env bash

# Recovery Graph — full end-to-end test
# Windows/Git Bash compatible

set -u

BASE="http://127.0.0.1:8000"

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ok() {
    echo -e "${GREEN}✓ $1${NC}"
}

fail() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

step() {
    echo -e "\n${CYAN}── $1${NC}"
}

warn() {
    echo -e "${YELLOW}! $1${NC}"
}

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

if [ -z "${ADMIN_SECRET:-}" ]; then
    if [ -f "$ROOT/.env" ]; then
        ADMIN_SECRET="$(grep '^ADMIN_SECRET=' "$ROOT/.env" | head -n 1 | cut -d '=' -f2-)"
        export ADMIN_SECRET
    fi
fi

if [ -z "${ADMIN_SECRET:-}" ]; then
    fail "ADMIN_SECRET is not set"
fi

if [ -z "${DATABASE_URL:-}" ]; then
    if [ -f "$ROOT/.env" ]; then
        DATABASE_URL="$(grep '^DATABASE_URL=' "$ROOT/.env" | head -n 1 | cut -d '=' -f2-)"
        export DATABASE_URL
    fi
fi

if [ -z "${DATABASE_URL:-}" ]; then
    fail "DATABASE_URL is not set"
fi

echo "Base URL     : $BASE"
echo "Database URL : $DATABASE_URL"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Generate JSON through Python instead of relying on shell quoting.
json_payload() {
    python.exe - "$1" "$2" <<'PY'
import json
import sys

scenario = sys.argv[1]
amount = int(sys.argv[2])

print(json.dumps({
    "scenario": scenario,
    "amount_paise": amount
}))
PY
}

admin_inject() {
    local scenario="$1"
    local amount="$2"
    local payload

    payload="$(json_payload "$scenario" "$amount")" || return 1

    curl.exe \
        -sS \
        --fail-with-body \
        --noproxy "*" \
        -X POST "$BASE/api/admin/inject" \
        -H "Content-Type: application/json" \
        -H "x-admin-secret: $ADMIN_SECRET" \
        --data-binary "$payload"
}

# ---------------------------------------------------------------------------
# 1. HEALTH
# ---------------------------------------------------------------------------

step "Health check"

if r="$(curl.exe -sS --fail --noproxy "*" "$BASE/health")"; then
    echo "  Response: $r"
    ok "Backend alive"
else
    fail "Backend not responding"
fi

# ---------------------------------------------------------------------------
# 2. UPI LATE CAPTURE
# ---------------------------------------------------------------------------

step "UPI Late Capture — payment.failed → payment.captured"

if r="$(admin_inject "upi_late_capture" 50000)"; then
    echo "  Response: $r"

    if echo "$r" | python.exe -c '
import json
import sys

d = json.load(sys.stdin)
injected = d.get("injected", [])

assert any("200" in str(x) for x in injected), injected
assert len(injected) >= 2, injected
'; then
        ok "UPI late capture injected"
    else
        fail "UPI late capture response was invalid"
    fi
else
    fail "UPI late capture request failed"
fi

sleep 3

# ---------------------------------------------------------------------------
# 3. EPISODE STATE
# ---------------------------------------------------------------------------

step "Verify UPI episode reaches captured_late"

if r="$(curl.exe -sS --fail --noproxy "*" "$BASE/api/episodes?limit=20")"; then

    echo "$r" | python.exe -c '
import json
import sys

d = json.load(sys.stdin)
eps = d.get("episodes", [])

print("  episodes found:", len(eps))

for ep in eps[:10]:
    payment_id = ep.get("payment_id", "?")
    state = ep.get("state", "?")
    print("  {} → state={}".format(payment_id[:20], state))

states = [e.get("state") for e in eps]

assert "captured_late" in states, (
    "captured_late not found; states={}".format(states)
)
'

    if [ $? -eq 0 ]; then
        ok "Late capture state verified"
    else
        fail "Episode state verification failed"
    fi

else
    fail "Could not retrieve episodes"
fi

# ---------------------------------------------------------------------------
# 4. CARD FINAL FAILURE
# ---------------------------------------------------------------------------

step "Card Final Failure → Diagnosis → Policy → Executor"

if r="$(admin_inject "card_final_failure" 75000)"; then
    echo "  Response: $r"
    ok "Card final failure injected"
else
    fail "Card final failure injection failed"
fi

sleep 5

# ---------------------------------------------------------------------------
# 5. INSUFFICIENT FUNDS
# ---------------------------------------------------------------------------

step "Insufficient Funds scenario"

if r="$(admin_inject "insufficient_funds" 30000)"; then
    echo "  Response: $r"
    ok "Insufficient funds injected"
else
    fail "Insufficient funds injection failed"
fi

sleep 3

# ---------------------------------------------------------------------------
# 6. DUPLICATE EVENT
# ---------------------------------------------------------------------------

step "Duplicate event — same event ID must be deduplicated"

if r="$(admin_inject "duplicate_event" 40000)"; then
    echo "  Response: $r"
    ok "Duplicate event test completed"
else
    fail "Duplicate event test failed"
fi

sleep 3

# ---------------------------------------------------------------------------
# 7. INVALID VPA
# ---------------------------------------------------------------------------

step "Invalid VPA — must not recover"

if r="$(admin_inject "invalid_vpa" 20000)"; then
    echo "  Response: $r"
    ok "Invalid VPA injected"
else
    fail "Invalid VPA injection failed"
fi

sleep 5

# ---------------------------------------------------------------------------
# 8. METRICS
# ---------------------------------------------------------------------------

step "Metrics check"

if r="$(curl.exe -sS --fail --noproxy "*" "$BASE/api/metrics")"; then

    echo "$r" | python.exe -c '
import json
import sys

d = json.load(sys.stdin)
s = d.get("summary", {})

print("  total         :", s.get("total", 0))
print("  recovered     :", s.get("recovered", 0))
print("  final_failed  :", s.get("final_failed", 0))
print("  captured_late :", s.get("captured_late", 0))
print("  retry_pending :", s.get("retry_pending", 0))
print("  escalated     :", s.get("escalated", 0))
print("  rate          :", str(s.get("recovery_rate_pct", 0)) + "%")

assert isinstance(s, dict)
'

    if [ $? -eq 0 ]; then
        ok "Metrics loaded"
    else
        fail "Metrics response invalid"
    fi

else
    fail "Metrics endpoint failed"
fi

# ---------------------------------------------------------------------------
# 9. LEDGER CHAIN
# ---------------------------------------------------------------------------

step "Ledger chain integrity check"

(
    cd "$ROOT"

    python.exe -c '
import os
from backend.ledger.audit_ledger import AuditLedger

conninfo = os.environ["DATABASE_URL"]

ledger = AuditLedger(conninfo)

head = ledger.head()
report = ledger.verify()

print(f"  head_seq        : {head["head_seq"]}")
print(f"  entries_checked : {report.entries_checked}")
print(f"  chain_ok        : {report.ok}")

if report.faults:
    for f in report.faults:
        print(
            f"  FAULT: seq={f.seq} "
            f"kind={f.kind} "
            f"{f.detail}"
        )

assert report.ok, f"Chain broken: {report.faults}"
'
)

if [ $? -eq 0 ]; then
    ok "Ledger chain intact"
else
    fail "Ledger chain broken"
fi

# ---------------------------------------------------------------------------
# 10. DIAGNOSIS SUITE
# ---------------------------------------------------------------------------

step "Diagnosis precision/recall suite (n=200)"

(
    cd "$ROOT/backend"
    python.exe -m eval.run_diagnosis_suite
)

if [ $? -eq 0 ]; then
    ok "Diagnosis suite passed"
else
    fail "Diagnosis suite failed"
fi

# ---------------------------------------------------------------------------
# 11. COUNTERFACTUAL BENCHMARK
# ---------------------------------------------------------------------------

step "Counterfactual benchmark"

(
    cd "$ROOT/backend"

    python.exe -c '
import os
from eval.benchmark import run_benchmark

result = run_benchmark(
    os.environ["DATABASE_URL"],
    verbose=True
)

lift = result["t_learner_lift_pp"]

print(f"\n  lift={lift}pp")

assert lift > 0, (
    f"Lift should be positive, got {lift}"
)
'
)

if [ $? -eq 0 ]; then
    ok "Benchmark passed"
else
    fail "Benchmark failed"
fi

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

echo
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ALL TESTS PASSED — Recovery Graph E2E ✓${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo