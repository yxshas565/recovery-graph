# Recovery Graph

> **Autonomous payment-failure recovery with reconciliation, deterministic safety controls, causal diagnosis, and an auditable recovery ledger.**

**Razorpay AI Buildathon 2026 · Track 03 — AI Revenue Recovery**

Recovery Graph is an autonomous payment recovery system designed around a simple principle:

> **LLMs may propose recovery intents. Deterministic software owns money, limits, retries, idempotency, and execution. Always.**

The system listens to Razorpay payment events, reconstructs the lifecycle of a failed payment into an explicit episode, determines whether recovery is safe, executes only policy-approved actions, and records the complete decision path in a tamper-evident hash-chained ledger.

Its central problem is not simply **"payment failed → retry payment."**

It is:

> **Was the payment actually final, or did a provisional failure later become a successful capture?**

Recovery Graph treats that distinction as a first-class state-machine problem.

---

## Table of Contents

- [Overview](#overview)
- [Problem](#problem)
- [What Recovery Graph Does](#what-recovery-graph-does)
- [Core Insight: Failure Is Not Always Final](#core-insight-failure-is-not-always-final)
- [Architecture](#architecture)
- [End-to-End Data Flow](#end-to-end-data-flow)
- [Payment Episode State Machine](#payment-episode-state-machine)
- [Diagnosis Engine](#diagnosis-engine)
- [Safety Model](#safety-model)
- [Policy Gate](#policy-gate)
- [Recovery Executor](#recovery-executor)
- [Idempotency and Duplicate Protection](#idempotency-and-duplicate-protection)
- [Immutable Audit Ledger](#immutable-audit-ledger)
- [Evaluation and Counterfactual Benchmark](#evaluation-and-counterfactual-benchmark)
- [Production-Style Demo](#production-style-demo)
- [Validated E2E Results](#validated-e2e-results)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Local Development](#local-development)
- [Docker](#docker)
- [Razorpay Webhooks](#razorpay-webhooks)
- [Running the E2E Suite](#running-the-e2e-suite)
- [Admin Scenario Injection](#admin-scenario-injection)
- [Evaluation Commands](#evaluation-commands)
- [Frontend](#frontend)
- [API Surface](#api-surface)
- [Security and Operational Boundaries](#security-and-operational-boundaries)
- [Failure Scenarios](#failure-scenarios)
- [Observability](#observability)
- [Windows / Git Bash Notes](#windows--git-bash-notes)
- [Known Evaluation Limitations](#known-evaluation-limitations)
- [Fresh Setup Checklist](#fresh-setup-checklist)
- [Demo Walkthrough](#demo-walkthrough)
- [Why This Architecture](#why-this-architecture)
- [Future Extensions](#future-extensions)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

# Overview

Recovery Graph is a payment-failure recovery agent built around **event reconciliation rather than naive retries**.

The system combines:

1. **Authenticated Razorpay webhook ingestion**
2. **Redis-backed event deduplication**
3. **Payment episode reconstruction**
4. **Explicit reconciliation state transitions**
5. **Rules-first failure diagnosis**
6. **LLM-assisted diagnosis for the long tail**
7. **Deterministic recovery policy enforcement**
8. **Bounded recovery execution**
9. **Append-only SHA-256 hash-chained audit logging**
10. **Live operational visualization**
11. **Synthetic counterfactual evaluation**
12. **End-to-end scenario validation**

The result is a system where an operator can trace a payment from:

```text
Webhook
   ↓
Event authentication
   ↓
Deduplication
   ↓
Payment episode
   ↓
Diagnosis
   ↓
Policy
   ↓
Executor
   ↓
Outcome
   ↓
Audit ledger
```

The important architectural boundary is that **the probabilistic components never directly control payment execution**.

---

# Problem

Traditional payment-recovery automation often reduces the problem to:

```text
payment.failed
       ↓
retry
```

That is unsafe.

A payment failure event can be provisional. A later event may indicate that the original payment eventually succeeded.

If a recovery system creates a second payment attempt immediately after the provisional failure, the customer can potentially be charged twice.

The correct question is therefore:

```text
Did the original payment actually reach a terminal failed state?
```

rather than:

```text
Did I receive a payment.failed event?
```

Recovery Graph addresses this using an explicit payment-episode state machine.

---

# What Recovery Graph Does

Recovery Graph performs the following pipeline:

```text
1. Receive Razorpay webhook
2. Verify webhook authenticity
3. Deduplicate the event
4. Extract payment state and failure information
5. Reconcile the event into a payment episode
6. Determine whether the failure is provisional or final
7. Diagnose the failure class
8. Generate a typed recovery intent
9. Pass the intent through a deterministic policy gate
10. Enforce safety constraints
11. Execute only an approved recovery action
12. Observe the resulting payment events
13. Attribute the outcome to the intervention
14. Append the complete decision path to the audit ledger
```

The system is deliberately designed so that **diagnosis and execution are separate concerns**.

---

# Core Insight: Failure Is Not Always Final

The most important recovery scenario implemented in Recovery Graph is:

```text
payment.failed
      ↓
provisional_failed
      ↓
payment.captured
      ↓
captured_late
```

When the later capture belongs to the same payment ID, Recovery Graph does **not** create a recovery payment.

Instead:

```text
payment.failed
      ↓
wait/reconcile
      ↓
payment.captured
      ↓
mark original payment as captured_late
      ↓
suppress recovery
```

This is fundamentally different from a retry-first recovery system.

The payment lifecycle is treated as an **event-sourced reconciliation problem**.

---

# Architecture

```text
                         Razorpay
                            │
                            │ Webhooks
                            ▼
                 ┌──────────────────────┐
                 │   Webhook Ingestor   │
                 │                      │
                 │ HMAC verification    │
                 │ Event parsing        │
                 │ Redis deduplication  │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Reconciliation       │
                 │ State Machine        │
                 │                      │
                 │ Payment episode      │
                 │ lifecycle tracking   │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Diagnosis Engine     │
                 │                      │
                 │ Rules-first          │
                 │ + LLM tail           │
                 │ + typed intent       │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Deterministic        │
                 │ Policy Gate          │
                 │                      │
                 │ Amount limits        │
                 │ Retry limits         │
                 │ Failure semantics    │
                 │ Safety constraints   │
                 └──────────┬───────────┘
                            │
                    approved intent
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Recovery Executor    │
                 │                      │
                 │ Bounded actions      │
                 │ Idempotent refs      │
                 │ Razorpay APIs        │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Hash-Chain Ledger    │
                 │                      │
                 │ PostgreSQL           │
                 │ SHA-256              │
                 │ Append-only audit    │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ React Operations     │
                 │ Console              │
                 │                      │
                 │ Live operations      │
                 │ Episodes             │
                 │ Architecture         │
                 │ Evaluation           │
                 │ Demo scenarios       │
                 └──────────────────────┘
```

---

# End-to-End Data Flow

A typical payment failure flows through the system as follows:

```text
Razorpay
   │
   │ payment.failed
   ▼
Webhook endpoint
   │
   ├── Verify HMAC-SHA256 signature
   │
   ├── Check event ID in Redis
   │
   └── Persist event
   │
   ▼
Payment Episode
   │
   ├── payment ID
   ├── amount
   ├── method
   ├── failure reason
   ├── timestamps
   └── lifecycle state
   │
   ▼
Diagnosis
   │
   ├── deterministic classification
   └── LLM-assisted long-tail reasoning
   │
   ▼
Typed Recovery Intent
   │
   ▼
Deterministic Policy Gate
   │
   ├── allowed?
   ├── safe?
   ├── within limits?
   ├── retry budget available?
   └── idempotency valid?
   │
   ├───────────────┐
   │               │
 blocked         approved
   │               │
   ▼               ▼
audit           executor
                    │
                    ▼
               Razorpay
                    │
                    ▼
                outcome
                    │
                    ▼
             audit ledger
```

---

# Payment Episode State Machine

Recovery Graph explicitly models payment recovery as a finite lifecycle.

| State | Meaning |
|---|---|
| `provisional_failed` | `payment.failed` received, but the failure is not yet treated as final |
| `retry_pending` | A recovery action has been approved/executed and the system is awaiting the resulting payment |
| `captured_late` | The original payment later arrived as captured; recovery is suppressed |
| `final_failed` | The payment remained failed after the reconciliation window |
| `recovered` | A recovery intervention resulted in a successful payment |
| `escalated` | The policy layer rejected available automated recovery paths |

The important transition is:

```text
provisional_failed
        │
        │ payment.captured
        ▼
captured_late
```

That transition prevents unnecessary second-payment recovery.

---

# Diagnosis Engine

Recovery Graph uses a **rules-first + LLM-tail** diagnosis architecture.

The objective is not to ask an LLM to make an unrestricted payment decision.

Instead, diagnosis is separated from execution.

## Rules-first layer

Known and deterministic failure classes can be identified using structured payment information such as:

- payment method
- error code
- error reason
- error source
- error step
- VPA information
- card information
- payment lifecycle state

This provides deterministic handling for known failure classes.

## LLM tail

The LLM is used where structured signals are insufficient or ambiguous.

Its role is to produce a structured diagnosis/recovery intent rather than directly invoke a payment API.

Conceptually:

```text
Raw payment evidence
        ↓
Diagnosis model
        ↓
Typed diagnosis
        ↓
Typed recovery intent
        ↓
Deterministic policy
        ↓
Executor
```

The LLM is therefore **advisory**, not sovereign.

---

# Safety Model

The central safety invariant is:

> **An LLM can propose. Deterministic code decides.**

Recovery Graph never allows an LLM to directly execute a payment action.

The execution boundary is:

```text
                 probabilistic
                     world
                       │
                       ▼
               Diagnosis Agent
                       │
                       │ typed intent
                       ▼
             ┌───────────────────┐
             │   POLICY GATE     │
             │                   │
             │ deterministic     │
             │ constraints       │
             └─────────┬─────────┘
                       │
                  approved only
                       │
                       ▼
                  EXECUTOR
                       │
                       ▼
                 Payment API
```

The policy layer owns:

- money-related decisions
- recovery eligibility
- retry limits
- action constraints
- idempotency requirements
- failure-class restrictions
- execution authorization

This creates a hard boundary between **reasoning** and **money movement**.

---

# Policy Gate

The policy gate is the only authorized entry point to the recovery executor.

A proposed recovery action must satisfy deterministic constraints before execution.

Conceptually:

```text
diagnosis
   +
failure evidence
   +
payment state
   +
recovery history
        │
        ▼
   POLICY GATE
        │
   ┌────┴────┐
   │         │
reject     approve
   │         │
   ▼         ▼
 audit     executor
```

This means a highly confident diagnosis still cannot bypass the policy layer.

For example, an invalid VPA is not automatically retried merely because a model suggests "retry."

---

# Recovery Executor

The executor performs only actions that have passed the policy gate.

The recovery path is designed around:

- bounded actions
- explicit payment references
- idempotent execution
- deterministic limits
- observable outcomes

The executor is intentionally kept separate from the diagnosis system.

This allows the system to change or improve diagnosis without granting additional execution authority.

---

# Idempotency and Duplicate Protection

Duplicate webhook delivery is expected in distributed payment systems.

Recovery Graph uses Redis-backed event deduplication.

Conceptually:

```text
event_id
   ↓
Redis
   │
   ├── unseen → process
   │
   └── seen   → suppress
```

The deduplication key is retained with an expiration window.

The E2E suite explicitly validates duplicate delivery.

Example:

```text
payment.failed
       ↓
processed

same event ID
       ↓
duplicate
       ↓
suppressed
```

This prevents the same webhook delivery from triggering the recovery pipeline repeatedly.

---

# Immutable Audit Ledger

Every important decision is recorded in an append-only PostgreSQL ledger.

Each ledger entry participates in a SHA-256 hash chain.

Conceptually:

```text
Entry N-1
   │
   ├── previous_hash
   │
   ▼
Entry N
   │
   ├── event
   ├── decision
   ├── actor
   ├── timestamp
   ├── payload
   └── hash
   │
   ▼
Entry N+1
```

The resulting structure makes the ledger tamper-evident.

A modified historical record would invalidate subsequent hashes.

The E2E validation explicitly verifies:

```text
head_seq        : 37
entries_checked : 37
chain_ok        : True
```

The evaluation workflow also records its own pre-registration and result information in the ledger.

---

# Evaluation and Counterfactual Benchmark

Recovery Graph includes a synthetic evaluation pipeline designed to evaluate both diagnosis and intervention effects.

The benchmark contains:

```text
200 synthetic payment episodes
10 failure classes
```

Failure classes include:

- insufficient funds
- user abandoned
- timeout / late authentication
- bank downtime
- wrong UPI PIN
- limit exceeded
- card do not honor
- invalid VPA
- expired card
- 3DS failure

The benchmark evaluates:

1. diagnosis quality
2. treatment/control differences
3. heterogeneous treatment effects
4. pre-registration integrity
5. ledger integrity

---

## Diagnosis Evaluation

The diagnosis suite was executed with:

```text
n = 200
```

Validated result:

```text
Correct   : 200/200
Precision : 1.000
Recall    : 1.000
```

That corresponds to:

```text
Accuracy  : 100%
Precision : 100%
Recall    : 100%
```

---

## Counterfactual Evaluation

The benchmark includes a T-learner estimator using a gradient-boosted-tree model.

Validated result:

```text
T-learner lift : +1.95pp
95% CI         : [-5.32pp, +10.33pp]
```

The corresponding incremental revenue estimate in the executed benchmark was:

```text
₹-33
```

The randomized-arm difference-in-means estimate was:

```text
+7.03pp
```

### Statistical interpretation

Recovery Graph **does not claim the +1.95pp T-learner estimate is statistically significant**.

The confidence interval:

```text
[-5.32pp, +10.33pp]
```

crosses zero.

The result is therefore reported as a **positive point estimate with substantial uncertainty**, rather than being presented as proof of a statistically significant uplift.

---

# Pre-Registration

The evaluation specification is registered before benchmark execution.

The validated workflow is:

```text
Pre-register evaluation specification
              ↓
        Generate dataset
              ↓
        Run estimators
              ↓
       Verify specification
              ↓
        Record benchmark
```

The executed benchmark produced:

```text
spec_hash:
08299875ab296a4a596cb1433fd8c142a86b2db4ad16dca23021c98473028c66
```

The ledger recorded:

```text
spec ledger sequence : 38
result ledger seq    : 39
```

The benchmark verified:

```text
spec hash verified : True
ledger chain ok    : True
```

This provides an auditable connection between the evaluation specification and the reported result.

---

# Production-Style Demo

The frontend contains dedicated operational views for:

- live recovery operations
- architecture
- demo scenarios
- evaluation evidence

The intended demo flow is:

```text
Live Demo
    │
    ├── UPI late capture
    ├── Card final failure
    ├── Insufficient funds
    ├── Duplicate event
    └── Invalid VPA

Architecture
    │
    └── system safety boundaries

Evaluation
    │
    ├── diagnosis metrics
    ├── counterfactual results
    ├── pre-registration
    └── ledger verification
```

---

# Validated E2E Results

The complete end-to-end suite has been executed successfully.

Final result:

```text
══════════════════════════════════════════════════════════
  ALL TESTS PASSED — Recovery Graph E2E ✓
══════════════════════════════════════════════════════════
```

## Health

```text
Backend alive ✓
```

## UPI Late Capture

```text
payment.failed
      ↓
payment.captured
      ↓
captured_late
```

Validated successfully.

## Card Final Failure

```text
payment.failed
      ↓
final failure
```

Validated successfully.

## Insufficient Funds

Validated successfully.

## Duplicate Event

The same event ID was delivered twice.

The system returned duplicate status for both injected deliveries in the scenario harness and completed the duplicate-event validation successfully.

## Invalid VPA

The invalid VPA scenario was injected successfully and verified as a non-recovery path.

## Final Metrics After E2E Run

```text
total          : 93
recovered      : 3
final_failed   : 36
captured_late  : 27
retry_pending  : 24
escalated      : 0
```

Recovery rate reported by the metrics endpoint:

```text
7.69%
```

## Ledger

```text
head_seq        : 37
entries_checked : 37
chain_ok        : True
```

## Diagnosis

```text
n          : 200
correct    : 200/200
precision  : 1.000
recall     : 1.000
```

## Counterfactual Benchmark

```text
T-learner lift : +1.95pp
95% CI         : [-5.32pp, +10.33pp]
```

Pre-registration:

```text
verified : True
```

Ledger integrity:

```text
verified : True
```

---

# Project Structure

```text
recovery-graph/
│
├── backend/
│   ├── api/
│   │   └── admin.py
│   │
│   ├── diagnosis/
│   │   └── ...
│   │
│   ├── eval/
│   │   └── benchmark.py
│   │
│   ├── ledger/
│   │   └── ...
│   │
│   ├── recovery/
│   │   └── ...
│   │
│   ├── webhook/
│   │   ├── ingestor.py
│   │   └── models.py
│   │
│   ├── main.py
│   └── ...
│
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── App.css
│       ├── ArchitecturePage.tsx
│       ├── DemoPage.tsx
│       ├── EvaluationPage.tsx
│       └── ...
│
├── docker-compose.yml
├── test_e2e.sh
├── README.md
├── .env.example
└── ...
```

---

# Technology Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI / Python |
| Agent orchestration | LangGraph |
| Diagnosis | Rules-first + LLM-assisted reasoning |
| Database | PostgreSQL |
| Database driver | psycopg |
| Event deduplication | Redis |
| Frontend | React + Vite |
| Visualization | Recharts |
| Payments | Razorpay APIs / webhooks |
| Audit ledger | PostgreSQL + SHA-256 hash chain |
| Infrastructure | Docker Compose |
| Evaluation | Python synthetic benchmark + causal estimators |
| Local webhook exposure | ngrok or equivalent tunnel |

---

# Prerequisites

For local development, install:

- Python 3.11+ / compatible Python environment
- Node.js
- npm
- Docker Desktop
- Git
- Razorpay test-mode credentials
- Anthropic API key if using the LLM diagnosis path
- ngrok or another HTTPS tunnel if receiving external Razorpay webhooks locally

Verify:

```bash
python --version
node --version
npm --version
git --version
docker --version
```

---

# Configuration

Create a local environment file:

```bash
cp .env.example .env
```

Populate the required secrets:

```dotenv
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/recovery_graph
REDIS_URL=redis://localhost:6379

ANTHROPIC_API_KEY=your_anthropic_api_key

ADMIN_SECRET=your_admin_secret
```

Never commit `.env`.

The repository's `.env.example` intentionally contains placeholders rather than real credentials.

---

# Local Development

## 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/recovery-graph.git
cd recovery-graph
```

## 2. Configure environment

```bash
cp .env.example .env
```

Fill in the required credentials.

## 3. Start PostgreSQL and Redis

```bash
docker compose up postgres redis -d
```

## 4. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

## 5. Start the backend

```bash
uvicorn main:app --reload --port 8000
```

The backend should be available at:

```text
http://127.0.0.1:8000
```

Health endpoint:

```text
GET /health
```

Expected response:

```json
{
  "status": "ok",
  "service": "recovery-graph"
}
```

## 6. Start the frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server is normally available at:

```text
http://localhost:5173
```

---

# Docker

The repository includes Docker Compose configuration for the primary infrastructure services.

Start the stack:

```bash
docker compose up -d
```

Check containers:

```bash
docker compose ps
```

Expected services include:

```text
postgres
redis
backend
```

For the Dockerized backend, the database and Redis addresses use Docker service names rather than host loopback addresses.

Inside Docker:

```text
PostgreSQL:
postgresql://postgres:postgres@postgres:5432/recovery_graph

Redis:
redis://redis:6379
```

From the Windows host, PostgreSQL is exposed on:

```text
127.0.0.1:5433
```

and the backend on:

```text
127.0.0.1:8000
```

This distinction is important:

```text
Host → PostgreSQL : 127.0.0.1:5433
Docker → PostgreSQL: postgres:5432
```

---

# Razorpay Webhooks

Recovery Graph uses Razorpay webhooks as the primary event source.

The webhook endpoint is:

```text
POST /webhooks/razorpay
```

The webhook pipeline performs:

```text
raw request body
       ↓
HMAC-SHA256 verification
       ↓
event parsing
       ↓
event ID deduplication
       ↓
payment extraction
       ↓
episode reconciliation
```

For local external webhook delivery, expose the backend:

```bash
ngrok http 8000
```

Then configure the Razorpay webhook endpoint using the HTTPS tunnel URL:

```text
https://<your-tunnel>/webhooks/razorpay
```

The webhook secret configured in Razorpay must match:

```dotenv
RAZORPAY_WEBHOOK_SECRET=...
```

---

# Running the E2E Suite

The repository contains a complete end-to-end validation script:

```text
test_e2e.sh
```

Run:

```bash
chmod +x test_e2e.sh
./test_e2e.sh
```

On Windows with Git Bash:

```bash
bash test_e2e.sh
```

The suite validates:

```text
1. Health
2. UPI late capture
3. Episode reconciliation
4. Card final failure
5. Insufficient funds
6. Duplicate event handling
7. Invalid VPA
8. Metrics
9. Ledger integrity
10. Diagnosis precision/recall
11. Counterfactual benchmark
12. Pre-registration verification
13. Final ledger verification
```

A successful run ends with:

```text
ALL TESTS PASSED — Recovery Graph E2E ✓
```

---

# Admin Scenario Injection

For deterministic demonstrations and E2E validation, the backend exposes an admin-only scenario injection endpoint.

```text
POST /api/admin/inject
```

Required header:

```text
x-admin-secret: <ADMIN_SECRET>
```

Example body:

```json
{
  "scenario": "upi_late_capture",
  "amount_paise": 50000
}
```

Available scenarios:

```text
upi_late_capture
card_final_failure
insufficient_funds
duplicate_event
invalid_vpa
```

These scenarios generate synthetic Razorpay-style webhook events and send them through the **same webhook ingestion path** used by the application.

This is important: the demo does not bypass the reconciliation system.

The injected event still passes through:

```text
admin scenario
      ↓
webhook endpoint
      ↓
signature verification
      ↓
deduplication
      ↓
episode reconciliation
      ↓
diagnosis
      ↓
policy
      ↓
outcome
      ↓
ledger
```

The injection endpoint is disabled when the application environment is set to production.

---

# Evaluation Commands

The evaluation benchmark can be run from the backend environment.

```bash
cd backend
python -m eval.benchmark
```

The benchmark performs:

```text
1. Pre-register evaluation specification
2. Hash specification
3. Generate synthetic dataset
4. Run estimators
5. Calculate treatment effects
6. Calculate heterogeneous treatment effects
7. Verify pre-registration
8. Verify ledger integrity
9. Record result
```

The benchmark uses 200 synthetic episodes across 10 failure classes.

---

# Frontend

The React console is designed as an operations and demonstration surface rather than a generic dashboard.

The major views are:

## Live Operations

Shows payment episodes and recovery activity as they move through the system.

## Demo

Provides deterministic scenarios for demonstrating:

- late capture
- final failure
- insufficient funds
- duplicate events
- invalid VPA

## Architecture

Explains the system's major components and, most importantly, the boundary between:

```text
AI reasoning
      ↓
deterministic policy
      ↓
money-moving executor
```

## Evaluation

Surfaces the benchmark evidence:

- diagnosis accuracy
- precision
- recall
- T-learner estimate
- confidence interval
- RCT/diff-in-means estimate
- pre-registration hash
- ledger integrity

---

# API Surface

The major application surfaces include:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Service health |
| `POST /webhooks/razorpay` | Razorpay webhook ingestion |
| `POST /api/admin/inject` | Deterministic demo/test scenario injection |
| `GET /api/admin/scenarios` | Available test scenarios |
| `GET /api/metrics` | Recovery metrics |
| Dashboard endpoints | Episodes, activity, and operational data |

The exact API implementation should be treated as the source of truth for request/response schemas.

---

# Security and Operational Boundaries

Recovery Graph is designed around explicit trust boundaries.

## 1. Webhook authenticity

Razorpay webhook signatures are verified using HMAC-SHA256 before the event is accepted.

## 2. Event idempotency

Redis prevents repeated processing of the same webhook event ID.

## 3. Deterministic execution

LLM output cannot directly invoke a payment API.

## 4. Policy ownership

The deterministic policy layer owns execution authorization.

## 5. Bounded recovery

Recovery actions are subject to explicit constraints rather than unrestricted model behavior.

## 6. Auditability

Important decisions are written to the append-only hash chain.

## 7. Admin isolation

Synthetic scenario injection requires a separate admin secret and is disabled in production.

## 8. Secrets

Real credentials belong only in `.env` or the deployment secret manager.

They must never be committed to source control.

---

# Failure Scenarios

Recovery Graph intentionally distinguishes between recoverable and non-recoverable situations.

## UPI late capture

```text
payment.failed
      ↓
provisional_failed
      ↓
payment.captured
      ↓
captured_late
```

Action:

```text
DO NOT CREATE A SECOND RECOVERY PAYMENT
```

---

## Card final failure

```text
payment.failed
      ↓
diagnosis
      ↓
policy
      ↓
bounded recovery path
```

---

## Insufficient funds

The failure is diagnosed using structured payment evidence and passed through the recovery policy.

The policy determines whether an automated recovery path is permitted.

---

## Duplicate event

```text
event ID already seen
       ↓
duplicate
       ↓
suppress
```

No second processing path is allowed.

---

## Invalid VPA

```text
invalid VPA
     ↓
diagnosis
     ↓
policy rejection
     ↓
no unsafe retry
```

The system intentionally demonstrates that **recovery does not mean retry everything**.

---

# Observability

Recovery Graph exposes operational state through its API and frontend.

Key metrics include:

```text
total
recovered
final_failed
captured_late
retry_pending
escalated
recovery rate
```

This makes it possible to distinguish:

```text
original payment eventually succeeded
```

from:

```text
recovery intervention succeeded
```

That distinction is essential for measuring whether recovery actually created incremental value.

---

# Windows / Git Bash Notes

The E2E harness is compatible with Windows Git Bash.

There are two important Windows-specific details.

## PostgreSQL port

When the test runner executes on the Windows host while PostgreSQL runs in Docker, use:

```text
postgresql://postgres:postgres@127.0.0.1:5433/recovery_graph
```

Inside Docker, use:

```text
postgresql://postgres:postgres@postgres:5432/recovery_graph
```

## `.env` line endings

Windows `.env` files can use CRLF line endings.

The E2E harness strips carriage returns when reading `ADMIN_SECRET` so that the resulting HTTP header contains only the actual secret.

The test harness also forces Python UTF-8 output so Unicode status messages work correctly under Windows.

These compatibility details are already incorporated into `test_e2e.sh`.

---

# Known Evaluation Limitations

The benchmark is deliberately transparent about what it does and does not establish.

## Synthetic evaluation

The 200-episode benchmark is synthetic.

It demonstrates the evaluation machinery and validates the recovery/diagnosis logic under controlled conditions; it is not evidence of production-scale causal performance.

## Confidence interval

The T-learner estimate was:

```text
+1.95pp
```

with:

```text
95% CI = [-5.32pp, +10.33pp]
```

Because the interval crosses zero, the result should **not** be interpreted as statistically significant.

## Treatment heterogeneity

The benchmark includes heterogeneous treatment-effect estimates by failure class.

Those estimates are useful for demonstrating the evaluation pipeline, but several classes have small sample sizes.

Therefore, individual class-level estimates should be interpreted cautiously.

---

# Fresh Setup Checklist

For a clean environment:

```text
[ ] Clone repository
[ ] Copy .env.example → .env
[ ] Configure Razorpay credentials
[ ] Configure webhook secret
[ ] Configure Anthropic key
[ ] Configure admin secret
[ ] Start PostgreSQL
[ ] Start Redis
[ ] Start backend
[ ] Start frontend
[ ] Verify /health
[ ] Configure Razorpay webhook/tunnel if required
[ ] Run E2E suite
[ ] Verify ledger chain
[ ] Run evaluation
```

Expected health response:

```json
{
  "status": "ok",
  "service": "recovery-graph"
}
```

Expected E2E conclusion:

```text
ALL TESTS PASSED — Recovery Graph E2E ✓
```

---

# Demo Walkthrough

The recommended judge/demo flow is designed around the three most important properties of the system.

---

## Scene 1 — The Core Problem: Late Capture

Open:

```text
Live Demo → UPI late capture
```

Run the scenario.

Show:

```text
payment.failed
      ↓
provisional_failed
      ↓
payment.captured
      ↓
captured_late
      ↓
recovery suppressed
```

Key explanation:

> **"The important distinction is that a failure event isn't necessarily a final payment failure. Recovery Graph reconciles the same payment before deciding whether another payment is necessary."**

This is the central product insight.

---

## Scene 2 — Duplicate Protection

Open:

```text
Live Demo → Duplicate event
```

Run the scenario.

Show:

```text
Event
  ↓
Idempotency
  ↓
Duplicate
  ↓
Suppressed
  ↓
Audit
```

Key explanation:

> **"Webhook delivery can be repeated. The same event ID cannot cause the recovery pipeline to execute twice."**

---

## Scene 3 — Unsafe Recovery Is Blocked

Open:

```text
Live Demo → Invalid VPA
```

Run the scenario.

Show:

```text
Event
  ↓
Diagnosis
  ↓
Policy
  ↓
Blocked
  ↓
Audit
```

Key explanation:

> **"Recovery Graph does not equate recovery with retry. The deterministic policy layer can explicitly reject a recovery action."**

---

## Scene 4 — Evidence

Open:

```text
Evaluation
```

Show:

```text
Diagnosis
200/200

Precision
1.000

Recall
1.000

T-learner
+1.95pp

95% CI
[-5.32pp, +10.33pp]

Diff-in-means
+7.03pp

Pre-registration
verified

Ledger
intact
```

Important explanation:

> **"The point estimate is positive, but the confidence interval crosses zero, so we do not claim statistical significance."**

This distinction is intentional.

---

## Scene 5 — Architecture

Open:

```text
Architecture
```

Point to:

```text
Diagnosis
    ↓
Typed Intent
    ↓
Policy Gate
    ↓
Executor
```

Key explanation:

> **"The core safety boundary is that probabilistic reasoning cannot directly move money. Deterministic policy owns execution."**

---

# Why This Architecture

Recovery Graph intentionally avoids the architecture:

```text
LLM
 ↓
Razorpay API
```

That architecture makes the model responsible for decisions that should be deterministic.

Instead:

```text
                LLM
                 │
          proposes intent
                 │
                 ▼
        deterministic policy
                 │
          validates limits
                 │
       validates payment state
                 │
       validates idempotency
                 │
                 ▼
              executor
                 │
                 ▼
            Razorpay
```

This provides several advantages:

### Safety

Money movement remains under deterministic control.

### Auditability

The system can explain which event, diagnosis, policy decision, and executor action produced an outcome.

### Reconciliation

The original payment lifecycle is tracked independently of recovery actions.

### Idempotency

Duplicate events and repeated execution attempts can be controlled explicitly.

### Model replaceability

The diagnosis model can change without redesigning the execution boundary.

### Evaluation

The intervention can be evaluated independently from the diagnostic model.

---

# Design Principles

Recovery Graph follows several non-negotiable principles.

## 1. Webhook truth beats browser state

The payment lifecycle is reconstructed from authoritative payment events rather than UI assumptions.

## 2. Failure is a state, not necessarily a conclusion

A `payment.failed` event can represent an intermediate condition.

## 3. Diagnose before recovering

The system determines what happened before deciding what to do.

## 4. Policy before execution

No recovery action reaches the executor without deterministic authorization.

## 5. Idempotency everywhere

Repeated events must not create repeated side effects.

## 6. Audit every important decision

The system records decisions and outcomes in a tamper-evident ledger.

## 7. Measure incremental recovery

A successful recovery is meaningful only if it creates an outcome that would not otherwise have happened.

## 8. Be honest about uncertainty

A positive point estimate is not automatically evidence of a statistically significant effect.

---

# Future Extensions

The architecture is intentionally extensible.

Potential future work includes:

- richer real-time causal attribution
- larger production-derived evaluation datasets
- online policy learning under strict safety constraints
- merchant-specific recovery policies
- adaptive reconciliation windows
- richer payment-method-specific recovery strategies
- automated anomaly detection over payment episodes
- stronger ledger replication and external anchoring
- production-grade secret management
- distributed worker execution
- richer operational alerting
- automated experiment assignment and monitoring
- formal policy verification

These extensions do not require removing the core safety boundary.

The intended evolution remains:

```text
Better intelligence
       ↓
better diagnosis
       ↓
better proposals
       ↓
same deterministic safety boundary
       ↓
controlled execution
```

---

# Repository Status

The current implementation has been validated end-to-end.

Final repository state:

```text
Branch:
main

Remote:
origin/main

Working tree:
clean
```

The complete E2E suite has passed after validating:

```text
✓ backend health
✓ webhook ingestion
✓ webhook signature path
✓ event deduplication
✓ UPI late capture reconciliation
✓ captured_late state
✓ card final failure
✓ insufficient funds
✓ invalid VPA
✓ metrics
✓ hash-chain ledger
✓ diagnosis suite
✓ counterfactual benchmark
✓ evaluation pre-registration
✓ evaluation ledger integrity
```

---

# License

This project was built for the Razorpay AI Buildathon 2026.

---

# Acknowledgements

Built for the **Razorpay AI Buildathon 2026 · Track 03 — AI Revenue Recovery**.

The project explores a safety-first approach to autonomous payment recovery where AI improves diagnosis and decision support while deterministic software retains control over money movement.

---

## Built By

**Yashas Sadananda**  
PES University

**Razorpay AI Buildathon 2026**

---

> **Recovery Graph**
>
> *Don't retry the payment.*
>
> *Reconstruct what actually happened.*
>
> *Then recover only when it is safe.*