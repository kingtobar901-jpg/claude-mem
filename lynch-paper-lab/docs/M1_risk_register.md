# M1 — Ranked Risk Register

Ranking = impact × likelihood (H/M/L). "Control" says what enforces each item and when it gets tested.

| # | Risk | Impact | Likelihood | Control | Status |
|---|---|---|---|---|---|
| 1 | **Accidental live order** (live URL or live key) | Critical | L | `lpl.safety` accepts only the paper host and `PK…` key IDs. DB CHECK on `run.broker_base_url`. Repo test fails on any live-host string. | Implemented and tested (M1). Key-prefix heuristic to re-check in M4. |
| 2 | **Survivorship bias** from incomplete free S&P membership history | H | H | Point-in-time membership table. Every report shows the coverage % and a survivorship caveat. Delisted names without prices count as "missing", never dropped silently. | Design only. Cannot be fully fixed with free data. |
| 3 | **Look-ahead bias** (restated adjusted prices, membership, fundamentals by period instead of filing date, current GICS) | H | H | As-of reads by `fetched_at_utc`. Adjustments rebuilt from actions known at t. DB CHECK `data_asof <= decision_ts`. M5 look-ahead unit tests (future-poisoning). | Schema guard tested. Engine in M5. |
| 4 | **Overfitting / multiple testing** | H | M | Hashed frozen config. `variant_registry` filled *before* runs. Holdout locked. Bootstrap CIs. Every variant counted in reports. | Lock tested. Registry schema done. |
| 5 | **Duplicate orders** on retry, timeout, or restart | H | M | Deterministic `client_order_id`, DB UNIQUE, broker uniqueness. On timeout: query by client_order_id before resubmitting. | ID and constraints tested. Broker behavior in M4. |
| 6 | **Ledger vs broker divergence** (partial fills, corporate actions, paper-sim quirks) | H | M | Daily reconciliation. Any discrepancy engages the kill switch. 20 clean sessions gate. | M4. |
| 7 | **Stale or bad data traded** (vendor outage, holiday, partial day) | H | M | Validation blocks batches with errors. Stale-data kill switch if latest session < expected session. Second-source reconciliation. | M2/M3. |
| 8 | **Free-tier limits** (Tiingo unique-symbol cap, Alpaca history from ~2016) make the full universe or long backtests impossible | M | H | Measure in M2. If insufficient: shorter backtest window stated plainly, or owner decides on alternatives. No silent substitution. | Open. |
| 9 | **Short history → weak holdout.** Momentum needs 13 months of warm-up. With about 10 years of data, the holdout is about 3 years and covers few regimes. | M | H | Report CIs, not point estimates. Accept "no edge found". | Open (decision D3). |
| 10 | **Execution model mismatch**: Alpaca paper fills are simulated and may ignore open auction slippage. `opg` and fractional-share support to be confirmed. | M | M | Backtest uses the explicit cost model. Paper fills are compared with the modeled open in M6. | M4. |
| 11 | **Sector cap ambiguity** changes results depending on the overflow rule | M | M | Must be decided and frozen before any backtest (D1). | Open. |
| 12 | **Secrets leakage.** The repo is a **public fork**. | H | L | Env vars only. `.env` gitignored. Repo secret-scan test. Redacted repr. | Tested (M1). Recommend a private repo (D5). |
| 13 | **Ephemeral or unattended host** misses sessions or loses the DB | M | M | M7 scheduler on a persistent host. Startup recovery = reconcile before trading. Backups. | M7. |
| 14 | **Benchmark error** (price-only SPY instead of total return) flatters the strategy | M | M | Total-return SPY built from dividends and cross-checked against a vendor-adjusted series. | M5/M6. |
| 15 | **Demo UI confusion**: synthetic prices mistaken for real results; sign-in and persistence unverified | M | M | Dashboard reads only the ledger and shows the PAPER badge, label, and data age. Demo retired or watermarked. | M6/M7. |
| 16 | **Calendar/time-zone errors** (DST, half days, holidays) | M | L | NYSE calendar stored as data. All UTC. Tests across DST transitions. | M2. |
