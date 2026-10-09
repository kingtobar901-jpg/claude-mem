-- Immutable raw market-data store. UNVALIDATED / PAPER RESEARCH.
-- Rules:
--   * Every row belongs to exactly one fetch_batch (who/what/when fetched, payload hash).
--   * Nothing is ever UPDATEd or DELETEd (triggers below). Corrections arrive as new batches.
--   * Prices are stored as delivered (prefer raw/unadjusted) plus corporate actions; the signal
--     engine builds adjusted series as-of a decision timestamp from actions known by then.
--   * As-of read: for each (symbol, session_date) take the row from the latest batch with
--     fetched_at_utc <= :decision_ts_utc. Rows fetched after the decision are invisible.
-- Timestamps: ISO-8601 UTC with 'Z'. session_date: exchange-local trading date (America/New_York).

CREATE TABLE IF NOT EXISTS fetch_batch (
    batch_id        TEXT PRIMARY KEY,                 -- uuid4
    source          TEXT NOT NULL CHECK (source IN ('alpaca','tiingo','sec_edgar','constituents','fixture')),
    dataset         TEXT NOT NULL CHECK (dataset IN ('daily_bars','corporate_actions','index_membership','security_master','fundamentals')),
    request_json    TEXT NOT NULL,                    -- canonical JSON of request params (no secrets)
    fetched_at_utc  TEXT NOT NULL CHECK (fetched_at_utc LIKE '____-__-__T__:__:__%Z'),
    http_status     INTEGER,
    payload_sha256  TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    payload_path    TEXT NOT NULL,                    -- content-addressed raw response file: raw/<sha256>.json.gz
    row_count       INTEGER NOT NULL CHECK (row_count >= 0),
    code_version    TEXT NOT NULL                     -- git sha of the ingester
);

CREATE TABLE IF NOT EXISTS raw_daily_bar (
    batch_id          TEXT NOT NULL REFERENCES fetch_batch(batch_id),
    symbol            TEXT NOT NULL,
    session_date      TEXT NOT NULL CHECK (session_date LIKE '____-__-__'),
    open              REAL CHECK (open > 0),
    high              REAL CHECK (high > 0),
    low               REAL CHECK (low > 0),
    close             REAL NOT NULL CHECK (close > 0),
    volume            INTEGER CHECK (volume >= 0),
    adj_basis         TEXT NOT NULL CHECK (adj_basis IN ('raw','split','split_div')),
    vendor_adj_factor REAL,                           -- as delivered by vendor; audit only
    vendor_adj_close  REAL,                           -- as delivered by vendor; audit only
    PRIMARY KEY (batch_id, symbol, session_date),
    CHECK (high IS NULL OR low IS NULL OR high >= low)
);
CREATE INDEX IF NOT EXISTS ix_bar_symbol_date ON raw_daily_bar(symbol, session_date);

CREATE TABLE IF NOT EXISTS corporate_action (
    batch_id       TEXT NOT NULL REFERENCES fetch_batch(batch_id),
    symbol         TEXT NOT NULL,
    action_type    TEXT NOT NULL CHECK (action_type IN ('split','cash_dividend','spinoff','symbol_change','merger','delisting')),
    ex_date        TEXT NOT NULL,
    announced_date TEXT,                              -- NULL if source does not provide; treat known-at = fetched_at
    ratio          REAL,                              -- split: new/old shares
    cash_amount    REAL,                              -- per share, USD
    new_symbol     TEXT,
    PRIMARY KEY (batch_id, symbol, action_type, ex_date)
);

CREATE TABLE IF NOT EXISTS index_membership_event (
    batch_id        TEXT NOT NULL REFERENCES fetch_batch(batch_id),
    index_code      TEXT NOT NULL CHECK (index_code = 'SPX'),
    symbol          TEXT NOT NULL,
    event_type      TEXT NOT NULL CHECK (event_type IN ('add','remove')),
    effective_date  TEXT NOT NULL,
    announced_date  TEXT,
    source_ref      TEXT NOT NULL,                    -- URL / dataset id for audit
    PRIMARY KEY (batch_id, index_code, symbol, event_type, effective_date)
);

CREATE TABLE IF NOT EXISTS security_master (
    batch_id      TEXT NOT NULL REFERENCES fetch_batch(batch_id),
    symbol        TEXT NOT NULL,
    valid_from    TEXT NOT NULL,
    valid_to      TEXT,                               -- NULL = open
    name          TEXT,
    cik           TEXT,                               -- SEC Central Index Key
    gics_sector   TEXT,
    sector_source TEXT NOT NULL,                      -- documents non-point-in-time sector data
    PRIMARY KEY (batch_id, symbol, valid_from)
);

CREATE TABLE IF NOT EXISTS validation_result (
    validation_id  TEXT PRIMARY KEY,
    batch_id       TEXT NOT NULL REFERENCES fetch_batch(batch_id),
    check_name     TEXT NOT NULL CHECK (check_name IN ('duplicate','gap','stale_session','split_consistency','volume_consistency','ohlc_sanity','calendar')),
    severity       TEXT NOT NULL CHECK (severity IN ('info','warn','error')),
    symbol         TEXT,
    session_date   TEXT,
    detail_json    TEXT NOT NULL,
    run_at_utc     TEXT NOT NULL,
    code_version   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_reconciliation (
    recon_id            TEXT NOT NULL,
    primary_batch_id    TEXT NOT NULL REFERENCES fetch_batch(batch_id),
    secondary_batch_id  TEXT NOT NULL REFERENCES fetch_batch(batch_id),
    symbol              TEXT NOT NULL,
    session_date        TEXT NOT NULL,
    primary_close       REAL,
    secondary_close     REAL,
    abs_diff_bps        REAL,
    status              TEXT NOT NULL CHECK (status IN ('match','mismatch','missing_primary','missing_secondary')),
    run_at_utc          TEXT NOT NULL,
    PRIMARY KEY (recon_id, symbol, session_date)
);

-- Append-only enforcement.
CREATE TRIGGER IF NOT EXISTS ro_fetch_batch_u BEFORE UPDATE ON fetch_batch BEGIN SELECT RAISE(ABORT, 'append-only: fetch_batch'); END;
CREATE TRIGGER IF NOT EXISTS ro_fetch_batch_d BEFORE DELETE ON fetch_batch BEGIN SELECT RAISE(ABORT, 'append-only: fetch_batch'); END;
CREATE TRIGGER IF NOT EXISTS ro_raw_daily_bar_u BEFORE UPDATE ON raw_daily_bar BEGIN SELECT RAISE(ABORT, 'append-only: raw_daily_bar'); END;
CREATE TRIGGER IF NOT EXISTS ro_raw_daily_bar_d BEFORE DELETE ON raw_daily_bar BEGIN SELECT RAISE(ABORT, 'append-only: raw_daily_bar'); END;
CREATE TRIGGER IF NOT EXISTS ro_corporate_action_u BEFORE UPDATE ON corporate_action BEGIN SELECT RAISE(ABORT, 'append-only: corporate_action'); END;
CREATE TRIGGER IF NOT EXISTS ro_corporate_action_d BEFORE DELETE ON corporate_action BEGIN SELECT RAISE(ABORT, 'append-only: corporate_action'); END;
CREATE TRIGGER IF NOT EXISTS ro_index_membership_event_u BEFORE UPDATE ON index_membership_event BEGIN SELECT RAISE(ABORT, 'append-only: index_membership_event'); END;
CREATE TRIGGER IF NOT EXISTS ro_index_membership_event_d BEFORE DELETE ON index_membership_event BEGIN SELECT RAISE(ABORT, 'append-only: index_membership_event'); END;
CREATE TRIGGER IF NOT EXISTS ro_security_master_u BEFORE UPDATE ON security_master BEGIN SELECT RAISE(ABORT, 'append-only: security_master'); END;
CREATE TRIGGER IF NOT EXISTS ro_security_master_d BEFORE DELETE ON security_master BEGIN SELECT RAISE(ABORT, 'append-only: security_master'); END;
CREATE TRIGGER IF NOT EXISTS ro_validation_result_u BEFORE UPDATE ON validation_result BEGIN SELECT RAISE(ABORT, 'append-only: validation_result'); END;
CREATE TRIGGER IF NOT EXISTS ro_validation_result_d BEFORE DELETE ON validation_result BEGIN SELECT RAISE(ABORT, 'append-only: validation_result'); END;
CREATE TRIGGER IF NOT EXISTS ro_source_reconciliation_u BEFORE UPDATE ON source_reconciliation BEGIN SELECT RAISE(ABORT, 'append-only: source_reconciliation'); END;
CREATE TRIGGER IF NOT EXISTS ro_source_reconciliation_d BEFORE DELETE ON source_reconciliation BEGIN SELECT RAISE(ABORT, 'append-only: source_reconciliation'); END;
