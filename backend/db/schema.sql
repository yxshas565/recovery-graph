CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── EPISODES ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS episodes (
    id                  TEXT PRIMARY KEY,              -- episode:{payment_id}
    payment_id          TEXT NOT NULL UNIQUE,
    order_id            TEXT,
    subscription_id     TEXT,
    amount_paise        BIGINT NOT NULL,
    currency            TEXT NOT NULL DEFAULT 'INR',
    method              TEXT,                          -- upi/card/netbanking/wallet
    failure_class       TEXT,                          -- set by diagnosis agent
    state               TEXT NOT NULL DEFAULT 'created',
    -- created → provisional_failed → retry_pending →
    -- captured_late / final_failed / recovered / escalated
    contact             TEXT,
    email               TEXT,
    merchant_ref        TEXT,
    recovery_link_id    TEXT,                          -- plink_ id if created
    recovery_ref_id     TEXT,                          -- reference_id used on link
    recovery_amount     BIGINT,
    intervention_type   TEXT,
    attempts            INT NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    final_at            TIMESTAMPTZ,
    wait_until          TIMESTAMPTZ                    -- provisional_failed wait window
);

-- ── RAW WEBHOOK EVENTS ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS webhook_events (
    id                  TEXT PRIMARY KEY,              -- x-razorpay-event-id
    event_type          TEXT NOT NULL,                 -- payment.failed etc
    payment_id          TEXT,
    order_id            TEXT,
    subscription_id     TEXT,
    raw_payload         JSONB NOT NULL,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed           BOOLEAN NOT NULL DEFAULT FALSE,
    episode_id          TEXT REFERENCES episodes(id)
);

-- ── EPISODE ACTIONS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS episode_actions (
    id                  BIGSERIAL PRIMARY KEY,
    episode_id          TEXT NOT NULL REFERENCES episodes(id),
    action_key          TEXT NOT NULL UNIQUE,          -- idempotency key
    action_type         TEXT NOT NULL,
    -- wait / diagnose / negotiate / policy_check /
    -- create_link / capture_confirmed / escalate / deduplicated
    agent               TEXT NOT NULL,
    input_snapshot      JSONB NOT NULL,
    output_snapshot     JSONB NOT NULL,
    prompt_name         TEXT,
    prompt_sha256       TEXT,
    model_version       TEXT,
    razorpay_event_id   TEXT,
    razorpay_payment_id TEXT,
    razorpay_link_id    TEXT,
    state_before        TEXT NOT NULL,
    state_after         TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── DOWNTIME EVENTS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS downtime_events (
    id                  TEXT PRIMARY KEY,              -- down_xxx from Razorpay
    method              TEXT NOT NULL,
    status              TEXT NOT NULL,
    severity            TEXT,
    scheduled           BOOLEAN,
    begin_ts            TIMESTAMPTZ,
    end_ts              TIMESTAMPTZ,
    instrument          JSONB,
    raw_payload         JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── PROMPT REGISTRY ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_registry (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    version     TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    template    TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, version)
);

-- ── METRICS SNAPSHOTS ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id                      BIGSERIAL PRIMARY KEY,
    snapshot_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_episodes          INT NOT NULL DEFAULT 0,
    total_recovered         INT NOT NULL DEFAULT 0,
    total_final_failed      INT NOT NULL DEFAULT 0,
    total_captured_late     INT NOT NULL DEFAULT 0,
    total_escalated         INT NOT NULL DEFAULT 0,
    duplicate_prevented     INT NOT NULL DEFAULT 0,
    recovery_rate_pct       NUMERIC(6,3),
    median_recovery_min     NUMERIC(10,2),
    incremental_lift_pp     NUMERIC(6,3),
    cost_per_100_recovered  NUMERIC(10,4),
    by_failure_class        JSONB
);

-- ── EVAL PRE-REGISTRATION ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS eval_preregistrations (
    id              BIGSERIAL PRIMARY KEY,
    spec_hash       TEXT NOT NULL UNIQUE,
    spec_json       JSONB NOT NULL,
    ledger_seq      BIGINT,                            -- chain entry confirming timestamp
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unblinded_at    TIMESTAMPTZ,
    result_json     JSONB,
    deviations      JSONB
);

-- ── INDEXES ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_episodes_payment_id
    ON episodes(payment_id);

CREATE INDEX IF NOT EXISTS idx_episodes_state
    ON episodes(state);

CREATE INDEX IF NOT EXISTS idx_episodes_created_at
    ON episodes(created_at);

CREATE INDEX IF NOT EXISTS idx_webhook_events_pid
    ON webhook_events(payment_id);

CREATE INDEX IF NOT EXISTS idx_webhook_events_type
    ON webhook_events(event_type);

CREATE INDEX IF NOT EXISTS idx_episode_actions_epid
    ON episode_actions(episode_id);

CREATE INDEX IF NOT EXISTS idx_downtime_status
    ON downtime_events(status, method);

-- ── UPDATED_AT TRIGGER ───────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_episodes_updated_at
    BEFORE UPDATE ON episodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE TRIGGER trg_downtime_updated_at
    BEFORE UPDATE ON downtime_events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();