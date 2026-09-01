# Recovery Graph

Autonomous payment failure recovery agent with causal attribution — Razorpay AI Buildathon 2026, Track 01.

## What It Does

Recovery Graph listens to Razorpay webhooks, handles the documented `payment.failed → payment.captured` sequence correctly, classifies failures with a rules-first + LLM tail diagnosis engine, executes bounded recovery actions through a merchant agent negotiation layer, and attributes exactly which intervention recovered which rupee — all on an immutable hash-chained ledger.

## The Key Differentiator

Razorpay officially documents that `payment.failed` can be followed by `payment.captured` for the same payment ID (UPI in-app retry). Every other recovery agent ignores this — they fire a second payment link on a provisional failure, causing double charges. Recovery Graph handles this correctly with a reconciliation state machine.

## Architecture

```
Razorpay Webhooks
    → Webhook Ingestor (HMAC-SHA256 verify + Redis dedup)
    → Reconciliation State Machine (6 episode states)
    → LangGraph Agent Graph:
        → Diagnosis Agent (rules-first + LLM tail)
        → Policy Gate (deterministic — owns all money decisions)
        → Executor (Razorpay Payment Links with reference_id idempotency)
    → Hash-Chain Ledger (PostgreSQL, append-only, tamper-evident)
    → React Operations Console (SSE live feed + replay + counterfactual)
```

## Episode States

| State | Meaning |
|-------|---------|
| `provisional_failed` | payment.failed received — waiting for possible late capture |
| `retry_pending` | Recovery link created — awaiting payment |
| `captured_late` | Late capture arrived — NO recovery action taken |
| `final_failed` | Wait window elapsed — confirmed failed |
| `recovered` | Recovery payment captured |
| `escalated` | Policy gate rejected all options |

## Stack

- **Agent orchestration**: LangGraph (subagents-as-tools pattern)
- **Backend**: FastAPI + Python 3.11
- **Database**: PostgreSQL 16 + SQLAlchemy
- **Frontend**: React 18 + Vite + Recharts
- **Payment layer**: Razorpay test-mode APIs
- **Containerization**: Docker Compose
- **Ledger**: Append-only hash chain (SHA-256, gapless concurrent appends)

## Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/recovery-graph.git
cd recovery-graph

# 2. Environment
cp .env.example .env
# Fill in RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET, ANTHROPIC_API_KEY

# 3. Start infra
docker compose up postgres redis -d

# 4. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 5. Frontend
cd frontend
npm install
npm run dev

# 6. ngrok (for Razorpay webhooks)
ngrok http 8000
# Update webhook URL in Razorpay Dashboard to https://xxxx.ngrok.io/webhooks/razorpay
```

## End-to-End Test

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/recovery_graph
chmod +x test_e2e.sh
./test_e2e.sh
```

## The One Rule

> **LLMs propose typed intents. Deterministic code owns money, limits, IDs, and retries. Always.**

Every Razorpay API call has a `reference_id` as idempotency key. Webhook truth beats browser UI. PostgreSQL hash chain is the only source of truth. The policy gate is the only entry point to the executor.

## Eval

Pre-registered counterfactual evaluation using T-learner on 200 synthetic episodes across 10 failure classes. Incremental lift measured vs naive-retry baseline (T+1h/T+24h/T+72h schedule).

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/recovery_graph
cd backend
python -m eval.benchmark
```

## Razorpay API Surface

| API | Usage |
|-----|-------|
| Payment Webhooks | Primary truth source — authorized, captured, failed, downtime |
| Orders API | Status lookups, reconciliation |
| Payment Links API | Recovery path creation with `reference_id` idempotency |
| Payments API | Direct status fetch for reconciliation |
| Subscriptions | Recurring payment failure episodes |

---

Built by Yashas Sadananda · PES University · Razorpay AI Buildathon 2026