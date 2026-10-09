"""Apply schemas to SQLite databases. Raw store and ledger are separate files."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
SCHEMAS = ("store.sql", "ledger.sql")


def connect(path: str | Path, schema: str) -> sqlite3.Connection:
    if schema not in SCHEMAS:
        raise ValueError(schema)
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript((SCHEMA_DIR / schema).read_text())
    return conn
