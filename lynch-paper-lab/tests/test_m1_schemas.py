"""M1: schemas apply cleanly; append-only, idempotency, paper-endpoint and look-ahead constraints hold."""

import sqlite3
import unittest

from tests._paths import ROOT  # noqa: F401  (sets sys.path)
from lpl.db import connect
from lpl.ids import client_order_id

SHA = "a" * 64
TS = "2026-10-08T20:00:00Z"


def store():
    c = connect(":memory:", "store.sql")
    c.execute("INSERT INTO fetch_batch VALUES ('b1','fixture','daily_bars','{}',?,200,?,'raw/x.json.gz',1,'dev')", (TS, SHA))
    c.execute("INSERT INTO raw_daily_bar VALUES ('b1','AAPL','2026-10-08',1,2,0.5,1.5,100,'raw',NULL,NULL)")
    return c


def ledger():
    c = connect(":memory:", "ledger.sql")
    c.execute("INSERT INTO run VALUES ('r1','paper',?,?,'dev','https://paper-api.alpaca.markets')", (TS, SHA))
    c.execute("INSERT INTO risk_decision VALUES ('rk1','r1','2026-10-08','name_cap','pass','{}',?)", (TS,))
    return c


class TestStoreSchema(unittest.TestCase):
    def test_raw_bars_cannot_be_updated_or_deleted(self):
        c = store()
        for sql in ("UPDATE raw_daily_bar SET close = 9", "DELETE FROM raw_daily_bar",
                    "UPDATE fetch_batch SET row_count = 2", "DELETE FROM fetch_batch"):
            with self.subTest(sql=sql), self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                c.execute(sql)

    def test_duplicate_bar_in_same_batch_rejected(self):
        c = store()
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO raw_daily_bar VALUES ('b1','AAPL','2026-10-08',1,2,0.5,1.6,100,'raw',NULL,NULL)")

    def test_correction_is_a_new_batch_and_asof_read_respects_fetch_time(self):
        c = store()
        later = "2026-10-09T20:00:00Z"
        c.execute("INSERT INTO fetch_batch VALUES ('b2','fixture','daily_bars','{}',?,200,?,'raw/y.json.gz',1,'dev')", (later, "b" * 64))
        c.execute("INSERT INTO raw_daily_bar VALUES ('b2','AAPL','2026-10-08',1,2,0.5,1.7,100,'raw',NULL,NULL)")
        q = """SELECT r.close FROM raw_daily_bar r JOIN fetch_batch f USING(batch_id)
               WHERE r.symbol='AAPL' AND r.session_date='2026-10-08' AND f.fetched_at_utc <= ?
               ORDER BY f.fetched_at_utc DESC LIMIT 1"""
        self.assertEqual(c.execute(q, (TS,)).fetchone()[0], 1.5)       # decision before correction
        self.assertEqual(c.execute(q, (later,)).fetchone()[0], 1.7)    # decision after correction

    def test_bad_ohlc_rejected(self):
        c = store()
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO raw_daily_bar VALUES ('b1','MSFT','2026-10-08',1,0.4,0.5,1.5,100,'raw',NULL,NULL)")
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO raw_daily_bar VALUES ('b1','MSFT','2026-10-07',1,2,0.5,-1,100,'raw',NULL,NULL)")


class TestLedgerSchema(unittest.TestCase):
    def test_paper_run_requires_paper_endpoint(self):
        c = connect(":memory:", "ledger.sql")
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO run VALUES ('r2','paper',?,?,'dev','https://example.com')", (TS, SHA))
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO run VALUES ('r3','paper',?,?,'dev',NULL)", (TS, SHA))

    def test_duplicate_client_order_id_rejected(self):
        c = ledger()
        cid = client_order_id("AAPL", "mom_12_1", "2026-10-08", SHA)
        row = (cid, "r1", "2026-10-08", "AAPL", "mom_12_1", "buy", "1.5", "market", "opg", "rk1", TS)
        c.execute("INSERT INTO order_intent VALUES (?,?,?,?,?,?,?,?,?,?,?)", row)
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO order_intent VALUES (?,?,?,?,?,?,?,?,?,?,?)", row)

    def test_one_intent_per_ticker_signal_session_even_with_different_id(self):
        c = ledger()
        base = ["r1", "2026-10-08", "AAPL", "mom_12_1", "buy", "1", "market", "opg", "rk1", TS]
        c.execute("INSERT INTO order_intent VALUES (?,?,?,?,?,?,?,?,?,?,?)", ["lpl1-a", *base])
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO order_intent VALUES (?,?,?,?,?,?,?,?,?,?,?)", ["lpl1-b", *base])

    def test_ledger_tables_append_only(self):
        c = ledger()
        c.execute("INSERT INTO cash_entry (run_id, entry_ts_utc, kind, amount_micros) VALUES ('r1',?,'deposit',100000000000)", (TS,))
        for sql in ("UPDATE cash_entry SET amount_micros = 0", "DELETE FROM cash_entry",
                    "UPDATE run SET mode='backtest'", "DELETE FROM risk_decision"):
            with self.subTest(sql=sql), self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                c.execute(sql)

    def test_signal_with_future_data_rejected(self):
        c = ledger()
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO signal (run_id, session_date, symbol, signal_name, eligible, decision_ts_utc, data_asof_utc) "
                      "VALUES ('r1','2026-10-08','AAPL','mom_12_1',1,?,'2026-10-09T00:00:00Z')", (TS,))

    def test_signal_label_cannot_be_changed(self):
        c = ledger()
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("INSERT INTO signal (run_id, session_date, symbol, signal_name, eligible, decision_ts_utc, data_asof_utc, label) "
                      "VALUES ('r1','2026-10-08','AAPL','mom_12_1',1,?,?,'VALIDATED')", (TS, TS))


class TestClientOrderId(unittest.TestCase):
    def test_deterministic_and_distinct(self):
        a = client_order_id("AAPL", "mom_12_1", "2026-10-08", SHA)
        self.assertEqual(a, client_order_id("AAPL", "mom_12_1", "2026-10-08", SHA))
        self.assertNotEqual(a, client_order_id("AAPL", "mom_12_1", "2026-10-09", SHA))
        self.assertNotEqual(a, client_order_id("MSFT", "mom_12_1", "2026-10-08", SHA))
        self.assertNotEqual(a, client_order_id("AAPL", "mom_12_1", "2026-10-08", "b" * 64))
        self.assertTrue(a.startswith("lpl1-20261008-AAPL-"))
        self.assertEqual(client_order_id("BRK.B", "mom_12_1", "2026-10-08", SHA)[:19], "lpl1-20261008-BRK_B")

    def test_rejects_bad_input(self):
        for args in (("aapl", "s", "2026-10-08"), ("AAPL", "s", "20261008")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                client_order_id(*args, SHA)


if __name__ == "__main__":
    unittest.main()
