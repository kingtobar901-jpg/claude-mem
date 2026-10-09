"""M1: paper-only guard and secret hygiene."""

import unittest

from tests._paths import ROOT  # noqa: F401
from lpl.safety import (LiveTradingRefused, MissingCredentials, assert_paper_endpoint,
                        load_paper_credentials)

# Fake keys built at runtime so the repo secret scan never sees a key-shaped literal.
FAKE_PAPER_ID = "P" + "K" + "TESTONLY0000000000"
FAKE_LIVE_ID = "A" + "K" + "TESTONLY0000000000"
FAKE_SECRET = "s3cr3t-" + "x" * 30
LIVE_URL = "https://" + "api." + "alpaca.markets"


class TestPaperGuard(unittest.TestCase):
    def test_paper_endpoint_accepted(self):
        self.assertEqual(assert_paper_endpoint("https://paper-api.alpaca.markets/v2"),
                         "https://paper-api.alpaca.markets")

    def test_non_paper_endpoints_refused(self):
        for url in (LIVE_URL, "http://paper-api.alpaca.markets", "https://paper-api.alpaca.markets.evil.com",
                    "https://paper-api.alpaca.markets:8443", "https://data.alpaca.markets", ""):
            with self.subTest(url=url), self.assertRaises(LiveTradingRefused):
                assert_paper_endpoint(url)

    def test_live_key_refused(self):
        with self.assertRaises(LiveTradingRefused):
            load_paper_credentials({"APCA_API_KEY_ID": FAKE_LIVE_ID, "APCA_API_SECRET_KEY": FAKE_SECRET})

    def test_live_base_url_env_refused(self):
        with self.assertRaises(LiveTradingRefused):
            load_paper_credentials({"APCA_API_KEY_ID": FAKE_PAPER_ID, "APCA_API_SECRET_KEY": FAKE_SECRET,
                                    "APCA_API_BASE_URL": LIVE_URL})

    def test_missing_credentials(self):
        with self.assertRaises(MissingCredentials):
            load_paper_credentials({})

    def test_secrets_never_rendered(self):
        creds = load_paper_credentials({"APCA_API_KEY_ID": FAKE_PAPER_ID, "APCA_API_SECRET_KEY": FAKE_SECRET})
        for rendered in (repr(creds), str(creds), f"{creds}"):
            self.assertNotIn(FAKE_SECRET, rendered)
            self.assertNotIn(FAKE_PAPER_ID, rendered)


if __name__ == "__main__":
    unittest.main()
