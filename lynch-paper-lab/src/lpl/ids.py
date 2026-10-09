"""Deterministic client_order_id: one per (ticker, signal, session).

Retries of the same intent reuse the same ID, so the broker's uniqueness check
(and our UNIQUE constraint) turns a duplicate submit into a rejection, not a second order.
"""

from __future__ import annotations

import hashlib
import re

_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_LEN = 48  # Alpaca allows up to 128


def client_order_id(symbol: str, signal_name: str, session_date: str, config_sha256: str) -> str:
    if not _SYMBOL.match(symbol):
        raise ValueError(f"bad symbol {symbol!r}")
    if not _DATE.match(session_date):
        raise ValueError(f"bad session_date {session_date!r}")
    material = "|".join((symbol, signal_name, session_date, config_sha256))
    digest = hashlib.sha256(material.encode()).hexdigest()[:16]
    cid = f"lpl1-{session_date.replace('-', '')}-{symbol.replace('.', '_')}-{digest}"
    assert len(cid) <= MAX_LEN
    return cid
