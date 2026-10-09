"""Paper-only guard. Every broker client must obtain credentials through here.

Refuses anything that is not the Alpaca paper endpoint, and refuses key IDs that
do not look like paper keys (Alpaca paper key IDs start with "PK"; live ones with
"AK" — a heuristic, re-verified in M4). Secrets never appear in repr/str.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
PAPER_HOST = "paper-api.alpaca.markets"
PAPER_KEY_PREFIX = "PK"

ENV_KEY_ID = "APCA_API_KEY_ID"
ENV_SECRET = "APCA_API_SECRET_KEY"
ENV_BASE_URL = "APCA_API_BASE_URL"


class LiveTradingRefused(RuntimeError):
    """Raised when anything resembling a live endpoint or live key is seen. Stop and tell the owner."""


class MissingCredentials(RuntimeError):
    pass


def assert_paper_endpoint(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != PAPER_HOST or parsed.port not in (None, 443):
        raise LiveTradingRefused(f"Non-paper broker endpoint refused: host={parsed.hostname!r}")
    return f"https://{PAPER_HOST}"


@dataclass(frozen=True)
class PaperCredentials:
    key_id: str = field(repr=False)
    secret: str = field(repr=False)
    base_url: str = PAPER_BASE_URL

    def __repr__(self) -> str:
        return f"PaperCredentials(key_id={redact(self.key_id)}, secret=***, base_url={self.base_url})"

    __str__ = __repr__


def redact(value: str) -> str:
    return f"{value[:2]}***" if value else "<empty>"


def load_paper_credentials(env: dict[str, str] | None = None) -> PaperCredentials:
    env = os.environ if env is None else env
    base_url = assert_paper_endpoint(env.get(ENV_BASE_URL, PAPER_BASE_URL))
    key_id = env.get(ENV_KEY_ID, "")
    secret = env.get(ENV_SECRET, "")
    if not key_id or not secret:
        raise MissingCredentials(f"Set {ENV_KEY_ID} and {ENV_SECRET} in the environment.")
    if not key_id.startswith(PAPER_KEY_PREFIX):
        raise LiveTradingRefused(f"Key ID {redact(key_id)} is not a paper key (expected prefix {PAPER_KEY_PREFIX}).")
    return PaperCredentials(key_id=key_id, secret=secret, base_url=base_url)
