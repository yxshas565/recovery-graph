-- backend/ledger/schema.sql
-- Append-only hash-chained audit ledger
-- Applied AFTER backend/db/schema.sql

CREATE TABLE IF NOT EXISTS ledger_head (
    chain_id    TEXT PRIMARY KEY,
    last_seq    BIGINT NOT NULL DEFAULT 0,
    last_hash   TEXT   NOT NULL DEFAULT '0000000000000000000000000000000000000000000000000000000000000000'
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    chain_id      TEXT   NOT NULL,
    entry_seq     BIGINT NOT NULL,
    episode_id    TEXT   NOT NULL,
    event_type    TEXT   NOT NULL,
    payload       JSONB  NOT NULL,
    payload_canon TEXT   NOT NULL,
    payload_hash  TEXT   NOT NULL,
    prev_hash     TEXT   NOT NULL,
    entry_hash    TEXT   NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chain_id, entry_seq)
);

CREATE INDEX IF NOT EXISTS idx_ledger_episode
    ON ledger_entries(chain_id, episode_id);

CREATE INDEX IF NOT EXISTS idx_ledger_seq
    ON ledger_entries(chain_id, entry_seq);

-- Immutability triggers
CREATE OR REPLACE FUNCTION ledger_no_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'ledger_entries is append-only — updates are forbidden';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ledger_no_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'ledger_entries is append-only — deletes are forbidden';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ledger_check_prev()
RETURNS TRIGGER AS $$
DECLARE prev TEXT;
BEGIN
    SELECT last_hash INTO prev
    FROM ledger_head WHERE chain_id = NEW.chain_id;
    IF prev IS NULL THEN
        RAISE EXCEPTION 'no ledger_head row for chain %', NEW.chain_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ledger_no_update ON ledger_entries;
CREATE TRIGGER trg_ledger_no_update
    BEFORE UPDATE ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION ledger_no_update();

DROP TRIGGER IF EXISTS trg_ledger_no_delete ON ledger_entries;
CREATE TRIGGER trg_ledger_no_delete
    BEFORE DELETE ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION ledger_no_delete();