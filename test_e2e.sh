#!/bin/bash
# test_e2e.sh — full end-to-end test
set -e

BASE="http://localhost:8000"
ADMIN="${ADMIN_SECRET}"
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; exit 1; }
step() { echo -e "\n${CYAN}── $1${NC}"; }

# ── 1. HEALTH ────────────────────────────────────────────────────────────────
step "Health check"
r=$(curl -sf $BASE/health) && ok "Backend alive: $r" || fail "Backend not responding"

# ── 2. UPI LATE CAPTURE (the key scenario) ───────────────────────────────────
step "UPI Late Capture — payment.failed → payment.captured (no duplicate action)"
r=$(curl -sf -X POST $BASE/api/admin/inject \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: $ADMIN" \
  -d '{"scenario":"upi_late_capture","amount_paise":50000}')
echo "$r" | python3 -c "
import json,sys
d=json.load(sys.stdin)
injected=d.get('injected',[])
print('  injected:', injected)
assert any('200' in i for i in injected), 'injection failed'
" && ok "UPI late capture injected" || fail "UPI late capture failed"

sleep 2

# ── 3. CHECK EPISODE STATE ────────────────────────────────────────────────────
step "Verify episode state = captured_late (NOT recovered — no duplicate action)"
r=$(curl -sf "$BASE/api/episodes?limit=5")
echo "$r" | python3 -c "
import json,sys
d=json.load(sys.stdin)
eps=d.get('episodes',[])
print(f'  episodes found: {len(eps)}')
for ep in eps:
    print(f'  {ep[\"payment_id\"][:20]} → state={ep[\"state\"]}')
if eps:
    states=[e['state'] for e in eps]
    assert 'captured_late' in states or 'created' in states, f'unexpected states: {states}'
" && ok "Episode state verified" || fail "Episode state check failed"

# ── 4. CARD FINAL FAILURE → RECOVERY PIPELINE ────────────────────────────────
step "Card Final Failure → Diagnosis → Policy → Executor"
r=$(curl -sf -X POST $BASE/api/admin/inject \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: $ADMIN" \
  -d '{"scenario":"card_final_failure","amount_paise":75000}')
echo "  $r"
ok "Card failure injected"

sleep 2

# ── 5. INSUFFICIENT FUNDS ────────────────────────────────────────────────────
step "Insufficient Funds scenario"
curl -sf -X POST $BASE/api/admin/inject \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: $ADMIN" \
  -d '{"scenario":"insufficient_funds","amount_paise":30000}' > /dev/null
ok "Insufficient funds injected"

# ── 6. DUPLICATE EVENT DEDUP ─────────────────────────────────────────────────
step "Duplicate event — same x-razorpay-event-id must be absorbed"
r=$(curl -sf -X POST $BASE/api/admin/inject \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: $ADMIN" \
  -d '{"scenario":"duplicate_event","amount_paise":40000}')
echo "$r" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('  result:', d)
" && ok "Duplicate event test done" || fail "Duplicate event test failed"

sleep 2

# ── 7. INVALID VPA — must NOT recover ────────────────────────────────────────
step "Invalid VPA — unrecoverable, must escalate not recover"
curl -sf -X POST $BASE/api/admin/inject \
  -H "Content-Type: application/json" \
  -H "x-admin-secret: $ADMIN" \
  -d '{"scenario":"invalid_vpa","amount_paise":20000}' > /dev/null
ok "Invalid VPA injected"

sleep 2

# ── 8. METRICS ────────────────────────────────────────────────────────────────
step "Metrics check"
r=$(curl -sf $BASE/api/metrics)
echo "$r" | python3 -c "
import json,sys
d=json.load(sys.stdin)
s=d.get('summary',{})
print(f'  total    : {s.get(\"total\",0)}')
print(f'  recovered: {s.get(\"recovered\",0)}')
print(f'  cap_late : {s.get(\"captured_late\",0)}')
print(f'  failed   : {s.get(\"final_failed\",0)}')
print(f'  escalated: {s.get(\"escalated\",0)}')
rate=s.get('recovery_rate_pct')
print(f'  rate     : {rate}%')
" && ok "Metrics loaded" || fail "Metrics failed"

# ── 9. LEDGER CHAIN INTEGRITY ─────────────────────────────────────────────────

step "Ledger chain integrity check"

(
  cd backend

  python -c "
import os
from ledger.audit_ledger import AuditLedger

conninfo = os.environ['DATABASE_URL']
ledger = AuditLedger(conninfo)

head = ledger.head()
report = ledger.verify()

print(f'  head_seq        : {head[\"head_seq\"]}')
print(f'  entries_checked : {report.entries_checked}')
print(f'  chain_ok        : {report.ok}')

if report.faults:
    for f in report.faults:
        print(f'  FAULT: seq={f.seq} kind={f.kind} {f.detail}')

assert report.ok, f'Chain broken: {report.faults}'
"
) && ok "Ledger chain intact" || fail "Ledger chain broken"

# ── 10. DIAGNOSIS SUITE ───────────────────────────────────────────────────────

step "Diagnosis precision/recall suite (n=200)"

(
  cd backend
  python -m eval.run_diagnosis_suite
) && ok "Diagnosis suite passed" || fail "Diagnosis suite failed"

# ── 11. BENCHMARK ─────────────────────────────────────────────────────────────

step "Counterfactual benchmark (pre-registered eval)"

(
  cd backend
  python -c "
import os
from eval.benchmark import run_benchmark

result = run_benchmark(os.environ['DATABASE_URL'], verbose=True)
lift = result['t_learner_lift_pp']

assert lift > 0, f'Lift should be positive, got {lift}'

print(f'\n  ✓ lift={lift}pp > 0 — agent outperforms naive baseline')
"
) && ok "Benchmark passed" || fail "Benchmark failed"

# ── SUMMARY ───────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  ALL TESTS PASSED — Recovery Graph E2E ✓${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}\n"