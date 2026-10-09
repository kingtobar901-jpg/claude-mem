# Test Plan

Runner: `make test` (stdlib `unittest`, also pytest-compatible). Every milestone adds `tests/test_mN_*.py`. A milestone is "done" only when **all** tests pass. The output is pasted into its report.

Fault injection uses fakes, never the network: a fake Alpaca server (in-process HTTP stub) and fixture vendor payloads. Live paper-API smoke tests are opt-in (`LPL_PAPER_SMOKE=1`), use only the paper key, and are excluded from the default run.

| Milestone | "Done" test (must pass) | Key cases |
|---|---|---|
| **M1** | `test_m1_*` | Config hash lock holds; a rule edit breaks it; a PROPOSED config is not runnable. Config values match the brief. Schemas apply. UPDATE/DELETE abort on every table. Duplicate `client_order_id` rejected. One intent per (ticker, signal, session). As-of read ignores later corrections. Paper-only guard (live URL, lookalike hosts, live key, missing env). Secrets never rendered. Repo has no key-shaped strings or live host. |
| **M2** | `test_m2_*` | Re-ingesting an identical payload is idempotent (same hash → no new rows). Duplicate, gap, and stale-session detection on fixtures. Split day: price ratio vs action ratio, volume inverse. OHLC sanity. Two-source recon flags an injected 1% mismatch and a missing day. DST/holiday calendar. Raw payload hash verifies. |
| **M3** | `test_m3_*` (fault injection) | 5% name cap and 25% sector cap enforced on adversarial targets. Gross ≤ 100%. Daily-loss breach → shutdown + no orders. Stale data (latest bar older than expected session) → kill switch. Process killed mid-run → restart recovers from the ledger, reconciles first, and submits nothing twice. Manual kill switch blocks everything. |
| **M4** | `test_m4_*` (fault injection) | Retry after timeout, 5xx, dropped response, or crash between submit and record → **0 duplicate orders** across N≥1,000 randomized trials. Partial fills. Rejected orders. Cash ledger folds to the broker balance. Reconciliation catches an injected 1-share and a $0.01 discrepancy. |
| **M5** | `test_m5_*` | **Look-ahead:** poisoning all data after t (NaN or 10× prices) leaves signals at t unchanged. Membership as-of. Fills at open t+1 only. Cost model arithmetic. Trend-filter switch. Holdout access raises unless unlocked. Variant must be registered before running. Bootstrap reproducible with seed. Hand-computed 12-1 values on a 3-stock fixture. |
| **M6** | `test_m6_*` | Metric functions against hand-computed and reference values (CAGR, vol, MDD, Sharpe, Sortino, turnover, alpha/beta). SPY total return vs vendor-adjusted series. Dashboard always renders PAPER badge + label + data age (snapshot test). |
| **M7** | `test_m7_*` + manual checklist | Scheduler skips non-sessions. Alert fires on kill switch and recon failure. Status page shows true state. Sign-in persistence and Safari: Playwright WebKit run + manual iPhone check, both recorded. |

Readiness-gate evidence (tracked from M4 on): count of consecutive clean reconciliations (target 20), duplicate-order count under retry tests (target 0), stale-data and restart test status.
