"""M1: frozen-strategy config integrity and content matches the owner's spec."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests._paths import CONFIG
from lpl.config import (ConfigIntegrityError, ConfigNotFrozenError, canonical_hash,
                        load_config)


class TestConfigLock(unittest.TestCase):
    def test_lock_matches(self):
        cfg, digest = load_config(CONFIG, require_frozen=False)
        self.assertEqual(digest, canonical_hash(cfg))

    def test_proposed_config_is_not_runnable(self):
        # Signal engine must refuse until the owner approves and status becomes FROZEN.
        with self.assertRaises(ConfigNotFrozenError):
            load_config(CONFIG, require_frozen=True)

    def test_any_rule_change_breaks_lock(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / CONFIG.name
            shutil.copy(CONFIG, cfg)
            shutil.copy(CONFIG.with_suffix(".sha256"), cfg.with_suffix(".sha256"))
            cfg.write_text(cfg.read_text().replace("skip_sessions = 21", "skip_sessions = 20"))
            with self.assertRaises(ConfigIntegrityError):
                load_config(cfg, require_frozen=False)

    def test_comment_change_does_not_break_lock(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / CONFIG.name
            shutil.copy(CONFIG, cfg)
            shutil.copy(CONFIG.with_suffix(".sha256"), cfg.with_suffix(".sha256"))
            cfg.write_text(cfg.read_text() + "\n# harmless comment\n")
            load_config(cfg, require_frozen=False)


class TestConfigMatchesSpec(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, _ = load_config(CONFIG, require_frozen=False)

    def test_paper_only_and_labeled(self):
        self.assertEqual(self.cfg["meta"]["mode"], "paper_only")
        self.assertEqual(self.cfg["meta"]["label"], "UNVALIDATED / PAPER RESEARCH")

    def test_signal_is_12_1_momentum(self):
        s = self.cfg["signal"]
        self.assertEqual((s["lookback_sessions"], s["skip_sessions"]), (252, 21))
        self.assertIn("as_of_t", s["price_basis"])

    def test_portfolio_rules(self):
        p = self.cfg["portfolio"]
        self.assertEqual(p["selection"], "top_quintile")
        self.assertEqual(p["weighting"], "equal")
        self.assertEqual(p["rebalance"], "monthly")
        self.assertEqual(p["max_weight_per_name"], 0.05)
        self.assertEqual(p["max_weight_per_sector"], 0.25)
        self.assertFalse(p["leverage"])
        self.assertFalse(p["shorting"])

    def test_trend_filter(self):
        t = self.cfg["trend_filter"]
        self.assertEqual((t["reference_symbol"], t["sma_sessions"]), ("SPY", 200))

    def test_execution_and_costs(self):
        e = self.cfg["execution"]
        self.assertEqual((e["decision_time"], e["fill_time"]), ("close_of_t", "open_of_t_plus_1"))
        self.assertEqual(e["cost_bps_round_trip"], 10.0)

    def test_benchmark_total_return(self):
        b = self.cfg["benchmark"]
        self.assertEqual(b["symbol"], "SPY")
        self.assertEqual(b["basis"], "total_return_dividends_reinvested")

    def test_second_arm_not_enabled_before_predeclaration(self):
        self.assertFalse(self.cfg["second_arm"]["enabled"])


if __name__ == "__main__":
    unittest.main()
