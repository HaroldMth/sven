# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_aur_retry.py
# ============================================================
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.getcwd())

import requests
from sven.db.aur_db import AURDB
from sven.exceptions import AURError


class TestAurRpcRetry(unittest.TestCase):
    """
    AUR's RPC is a plain HTTPS GET — on a flaky-but-not-fully-down network
    (packet loss, transient connection resets), a single dropped attempt
    shouldn't be enough to fail the whole upgrade check when a retry a
    moment later would likely succeed. Mirror downloads already get this
    kind of resilience via mirror failover; the AUR check had none at all.
    """

    def setUp(self):
        self.db = AURDB()

    def test_succeeds_after_transient_failures(self):
        call_count = {"n": 0}

        def flaky_get(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise requests.exceptions.ConnectionError("simulated flaky network")
            resp = MagicMock()
            resp.raise_for_status = lambda: None
            resp.json = lambda: {"type": "success", "results": []}
            return resp

        with patch("requests.get", side_effect=flaky_get), \
             patch("time.sleep", return_value=None):  # don't actually wait in tests
            result = self.db._rpc("info", ["some-pkg"])
            self.assertEqual(call_count["n"], 3)
            self.assertEqual(result["type"], "success")

    def test_raises_after_exhausting_retries_on_total_outage(self):
        call_count = {"n": 0}

        def always_fails(*a, **kw):
            call_count["n"] += 1
            raise requests.exceptions.ConnectionError("simulated total outage")

        with patch("requests.get", side_effect=always_fails), \
             patch("time.sleep", return_value=None):
            with self.assertRaises(AURError) as ctx:
                self.db._rpc("info", ["some-pkg"])
            self.assertEqual(call_count["n"], 3, "must attempt exactly max_retries+1 times")
            self.assertIn("3 attempts", str(ctx.exception))

    def test_http_error_does_not_retry(self):
        """A real HTTP error response means the server answered — retrying
        won't help and just delays a real failure."""
        call_count = {"n": 0}

        def http_error(*a, **kw):
            call_count["n"] += 1
            resp = MagicMock()
            resp.raise_for_status = MagicMock(side_effect=requests.exceptions.HTTPError("500"))
            return resp

        with patch("requests.get", side_effect=http_error), \
             patch("time.sleep", return_value=None):
            with self.assertRaises(AURError):
                self.db._rpc("info", ["some-pkg"])
            self.assertEqual(call_count["n"], 1, "HTTP errors must not be retried")


if __name__ == "__main__":
    unittest.main()
