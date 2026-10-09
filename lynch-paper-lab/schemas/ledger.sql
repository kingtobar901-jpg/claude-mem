-- Append-only research + execution ledger. UNVALIDATED / PAPER RESEARCH.
-- Money: INTEGER micro-dollars (1 USD = 1_000_000). Quantities: TEXT decimal strings
-- parsed with Python Decimal. No floats in accounting. Current state (positions, cash,
-- order status) is always DERIVED by folding events; nothing is updated in place.

CREATE TABLE IF NOT EXISTS run (
    run_id           TEXT PRIMARY KEY,
    mode             TEXT NOT NULL CHECK (mode IN ('backtest','paper')),
    started_at_utc   TEXT NOT NULL,
    config_sha256    TEXT NOT NULL CHECK (length(config_sha256) = 64),
    code_version     TEXT NOT NULL,
    broker_base_url  TEXT CHECK (broker_base_url IS NULL OR broker_base_url = 'https://paper-api.alpaca.markets'),
    CHECK ((mode = 'paper') = (broker_base_url IS NOT NULL))
);

-- Every assessment the screener/strategy makes, including "not selected". Replaces the
-- prototype's missing assessment ledger; dedup is by primary key.
CREATE TABLE IF NOT EXISTS signal (
    run_id          TEXT NOT NULL REFERENCES run(run_id),
    session_date    TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    signal_name     TEXT NOT NULL,
    value           REAL,
    rank            INTEGER,
    eligible        INTEGER NOT NULL CHECK (eligible IN (0,1)),
    ineligible_reason TEXT,
    decision_ts_utc TEXT NOT NULL,
    data_asof_utc   TEXT NOT NULL,                  -- max fetched_at_utc of inputs used
    label           TEXT NOT NULL DEFAULT 'UNVALIDATED / PAPER RESEARCH' CHECK (label = 'UNVALIDATED / PAPER RESEARCH'),
    PRIMARY KEY (run_id, session_date, symbol, signal_name),
    CHECK (data_asof_utc <= decision_ts_utc)        -- look-ahead guard at the storage layer
);

CREATE TABLE IF NOT EXISTS target_weight (
    run_id        TEXT NOT NULL REFERENCES run(run_id),
    session_date  TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    weight_bp     INTEGER NOT NULL CHECK (weight_bp BETWEEN 0 AND 10000),   -- basis points of equity
    reason        TEXT NOT NULL,
    PRIMARY KEY (run_id, session_date, symbol)
);

CREATE TABLE IF NOT EXISTS risk_decision (
    risk_check_id   TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES run(run_id),
    session_date    TEXT NOT NULL,
    rule            TEXT NOT NULL CHECK (rule IN ('name_cap','sector_cap','gross_exposure','daily_loss','stale_data','kill_switch','reconciliation_gate')),
    outcome         TEXT NOT NULL CHECK (outcome IN ('pass','adjust','block','shutdown')),
    detail_json     TEXT NOT NULL,
    decided_at_utc  TEXT NOT NULL
);

-- One intent per (ticker, signal, session); client_order_id is deterministic (lpl.ids).
CREATE TABLE IF NOT EXISTS order_intent (
    client_order_id TEXT PRIMARY KEY CHECK (client_order_id LIKE 'lpl1-%'),
    run_id          TEXT NOT NULL REFERENCES run(run_id),
    session_date    TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    signal_name     TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('buy','sell')),
    qty             TEXT NOT NULL,
    order_type      TEXT NOT NULL CHECK (order_type IN ('market','limit')),
    time_in_force   TEXT NOT NULL CHECK (time_in_force IN ('opg','day','cls')),
    risk_check_id   TEXT NOT NULL REFERENCES risk_decision(risk_check_id),
    created_at_utc  TEXT NOT NULL,
    UNIQUE (run_id, session_date, symbol, signal_name)
);

CREATE TABLE IF NOT EXISTS order_event (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id TEXT NOT NULL REFERENCES order_intent(client_order_id),
    broker_order_id TEXT,
    event_type      TEXT NOT NULL CHECK (event_type IN ('submit_attempt','submit_error','accepted','rejected','partially_filled','filled','canceled','expired','duplicate_rejected')),
    attempt         INTEGER NOT NULL DEFAULT 1 CHECK (attempt >= 1),
    event_ts_utc    TEXT NOT NULL,
    raw_json        TEXT                            -- broker response, secrets stripped
);

CREATE TABLE IF NOT EXISTS fill (
    execution_id    TEXT PRIMARY KEY,               -- broker execution id (or synthetic in backtest)
    client_order_id TEXT NOT NULL REFERENCES order_intent(client_order_id),
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('buy','sell')),
    qty             TEXT NOT NULL,
    price_micros    INTEGER NOT NULL CHECK (price_micros > 0),
    filled_at_utc   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cash_entry (
    entry_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES run(run_id),
    entry_ts_utc    TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('deposit','buy','sell','modeled_cost','reg_fee','dividend','interest','broker_adjustment')),
    amount_micros   INTEGER NOT NULL,               -- signed: + inflow, - outflow
    ref_id          TEXT,                           -- execution_id / corporate action ref
    memo            TEXT
);

CREATE TABLE IF NOT EXISTS kill_switch_event (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_ts_utc TEXT NOT NULL,
    state        TEXT NOT NULL CHECK (state IN ('engaged','released')),
    actor        TEXT NOT NULL CHECK (actor IN ('manual','stale_data','daily_loss','reconciliation','startup_recovery')),
    reason       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS broker_reconciliation (
    recon_id            TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES run(run_id),
    session_date        TEXT NOT NULL,
    run_at_utc          TEXT NOT NULL,
    ledger_cash_micros  INTEGER NOT NULL,
    broker_cash_micros  INTEGER NOT NULL,
    positions_diff_json TEXT NOT NULL,              -- '{}' when clean
    status              TEXT NOT NULL CHECK (status IN ('clean','discrepancy')),
    UNIQUE (run_id, session_date, run_at_utc)
);

-- Multiple-testing record: every variant ever evaluated, registered BEFORE it is run.
CREATE TABLE IF NOT EXISTS variant_registry (
    variant_id        TEXT PRIMARY KEY,
    config_sha256     TEXT NOT NULL CHECK (length(config_sha256) = 64),
    registered_at_utc TEXT NOT NULL,
    hypothesis        TEXT NOT NULL,
    data_window       TEXT NOT NULL,
    touches_holdout   INTEGER NOT NULL CHECK (touches_holdout IN (0,1)),
    owner_approved    INTEGER NOT NULL CHECK (owner_approved IN (0,1))
);
CREATE TABLE IF NOT EXISTS variant_result (
    variant_id      TEXT NOT NULL REFERENCES variant_registry(variant_id),
    evaluated_at_utc TEXT NOT NULL,
    metrics_json    TEXT NOT NULL,
    PRIMARY KEY (variant_id, evaluated_at_utc)
);

-- Append-only enforcement.
CREATE TRIGGER IF NOT EXISTS ro_run_u BEFORE UPDATE ON run BEGIN SELECT RAISE(ABORT, 'append-only: run'); END;
CREATE TRIGGER IF NOT EXISTS ro_run_d BEFORE DELETE ON run BEGIN SELECT RAISE(ABORT, 'append-only: run'); END;
CREATE TRIGGER IF NOT EXISTS ro_signal_u BEFORE UPDATE ON signal BEGIN SELECT RAISE(ABORT, 'append-only: signal'); END;
CREATE TRIGGER IF NOT EXISTS ro_signal_d BEFORE DELETE ON signal BEGIN SELECT RAISE(ABORT, 'append-only: signal'); END;
CREATE TRIGGER IF NOT EXISTS ro_target_weight_u BEFORE UPDATE ON target_weight BEGIN SELECT RAISE(ABORT, 'append-only: target_weight'); END;
CREATE TRIGGER IF NOT EXISTS ro_target_weight_d BEFORE DELETE ON target_weight BEGIN SELECT RAISE(ABORT, 'append-only: target_weight'); END;
CREATE TRIGGER IF NOT EXISTS ro_risk_decision_u BEFORE UPDATE ON risk_decision BEGIN SELECT RAISE(ABORT, 'append-only: risk_decision'); END;
CREATE TRIGGER IF NOT EXISTS ro_risk_decision_d BEFORE DELETE ON risk_decision BEGIN SELECT RAISE(ABORT, 'append-only: risk_decision'); END;
CREATE TRIGGER IF NOT EXISTS ro_order_intent_u BEFORE UPDATE ON order_intent BEGIN SELECT RAISE(ABORT, 'append-only: order_intent'); END;
CREATE TRIGGER IF NOT EXISTS ro_order_intent_d BEFORE DELETE ON order_intent BEGIN SELECT RAISE(ABORT, 'append-only: order_intent'); END;
CREATE TRIGGER IF NOT EXISTS ro_order_event_u BEFORE UPDATE ON order_event BEGIN SELECT RAISE(ABORT, 'append-only: order_event'); END;
CREATE TRIGGER IF NOT EXISTS ro_order_event_d BEFORE DELETE ON order_event BEGIN SELECT RAISE(ABORT, 'append-only: order_event'); END;
CREATE TRIGGER IF NOT EXISTS ro_fill_u BEFORE UPDATE ON fill BEGIN SELECT RAISE(ABORT, 'append-only: fill'); END;
CREATE TRIGGER IF NOT EXISTS ro_fill_d BEFORE DELETE ON fill BEGIN SELECT RAISE(ABORT, 'append-only: fill'); END;
CREATE TRIGGER IF NOT EXISTS ro_cash_entry_u BEFORE UPDATE ON cash_entry BEGIN SELECT RAISE(ABORT, 'append-only: cash_entry'); END;
CREATE TRIGGER IF NOT EXISTS ro_cash_entry_d BEFORE DELETE ON cash_entry BEGIN SELECT RAISE(ABORT, 'append-only: cash_entry'); END;
CREATE TRIGGER IF NOT EXISTS ro_kill_switch_event_u BEFORE UPDATE ON kill_switch_event BEGIN SELECT RAISE(ABORT, 'append-only: kill_switch_event'); END;
CREATE TRIGGER IF NOT EXISTS ro_kill_switch_event_d BEFORE DELETE ON kill_switch_event BEGIN SELECT RAISE(ABORT, 'append-only: kill_switch_event'); END;
CREATE TRIGGER IF NOT EXISTS ro_broker_reconciliation_u BEFORE UPDATE ON broker_reconciliation BEGIN SELECT RAISE(ABORT, 'append-only: broker_reconciliation'); END;
CREATE TRIGGER IF NOT EXISTS ro_broker_reconciliation_d BEFORE DELETE ON broker_reconciliation BEGIN SELECT RAISE(ABORT, 'append-only: broker_reconciliation'); END;
CREATE TRIGGER IF NOT EXISTS ro_variant_registry_u BEFORE UPDATE ON variant_registry BEGIN SELECT RAISE(ABORT, 'append-only: variant_registry'); END;
CREATE TRIGGER IF NOT EXISTS ro_variant_registry_d BEFORE DELETE ON variant_registry BEGIN SELECT RAISE(ABORT, 'append-only: variant_registry'); END;
CREATE TRIGGER IF NOT EXISTS ro_variant_result_u BEFORE UPDATE ON variant_result BEGIN SELECT RAISE(ABORT, 'append-only: variant_result'); END;
CREATE TRIGGER IF NOT EXISTS ro_variant_result_d BEFORE DELETE ON variant_result BEGIN SELECT RAISE(ABORT, 'append-only: variant_result'); END;
