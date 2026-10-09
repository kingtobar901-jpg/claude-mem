"""M1: required deliverables exist; no secrets or live endpoints anywhere in the project."""

import re
import unittest

from tests._paths import ROOT

REQUIRED = [
    "README.md",
    "docs/M1_architecture.md",
    "docs/M1_risk_register.md",
    "docs/M1_test_plan.md",
    "config/strategy_baseline.v1.toml",
    "config/strategy_baseline.v1.sha256",
    "schemas/store.sql",
    "schemas/ledger.sql",
    "src/lpl/safety.py",
    "src/lpl/config.py",
    "src/lpl/ids.py",
    "experimental/README.md",
    ".gitignore",
]

SECRET_PATTERNS = [
    re.compile(r"\b[AP]K[A-Z0-9]{16,}\b"),                                   # Alpaca key IDs
    # quoted credential-like value; ALL_CAPS env-var names (e.g. "APCA_API_SECRET_KEY") are allowed
    re.compile(r"(?i)(secret|api[_-]?key|token)\s*[:=]\s*['\"](?-i:(?![A-Z0-9_]+['\"]))[A-Za-z0-9/+_\-]{16,}['\"]"),
]
LIVE_ENDPOINT = re.compile(r"(?<![\w-])api\.alpaca\.markets")                # paper-api.* does not match


def project_files():
    for p in ROOT.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".toml", ".sql", ".md", ".sha256", ".txt", ".json", ".yml", ".yaml", ""}:
            yield p


class TestRepo(unittest.TestCase):
    def test_required_files_exist(self):
        missing = [f for f in REQUIRED if not (ROOT / f).is_file()]
        self.assertEqual(missing, [])

    def test_no_secrets_committed(self):
        hits = [(str(p.relative_to(ROOT)), m.group(0)[:6])
                for p in project_files() for pat in SECRET_PATTERNS for m in pat.finditer(p.read_text(errors="ignore"))]
        self.assertEqual(hits, [])

    def test_no_live_endpoint_referenced(self):
        hits = [str(p.relative_to(ROOT)) for p in project_files() if LIVE_ENDPOINT.search(p.read_text(errors="ignore"))]
        self.assertEqual(hits, [])

    def test_env_files_ignored(self):
        ignore = (ROOT / ".gitignore").read_text().split()
        self.assertIn(".env", ignore)


if __name__ == "__main__":
    unittest.main()
