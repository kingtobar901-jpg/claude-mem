# Lynch Paper Lab

> **PAPER TRADING ONLY — UNVALIDATED / PAPER RESEARCH.** Not investment advice. No performance claims.

Autonomous paper-trading research system for S&P 500 stocks. Status: **M1 (architecture) — awaiting owner approval.**

- Architecture: [docs/M1_architecture.md](docs/M1_architecture.md)
- Risks: [docs/M1_risk_register.md](docs/M1_risk_register.md)
- Test plan: [docs/M1_test_plan.md](docs/M1_test_plan.md)
- Strategy rules (hash-locked): [config/strategy_baseline.v1.toml](config/strategy_baseline.v1.toml)

## Run tests

```bash
cd lynch-paper-lab
make test            # Python 3.11+, standard library only
```

## Credentials

Set these in the environment only (never in files):
`APCA_API_KEY_ID` (paper key, starts with `PK`), `APCA_API_SECRET_KEY`, and optionally `APCA_API_BASE_URL` (must be `https://paper-api.alpaca.markets`). Any other endpoint or key is refused.

## Changing strategy rules

Don't edit `strategy_baseline.v1.toml`. Create `v2`, run `make lock-config` for the new file, register the variant, and get owner sign-off first.
