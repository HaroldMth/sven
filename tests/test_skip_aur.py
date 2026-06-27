# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_skip_aur.py
# ============================================================
import sys
import os
import unittest

sys.path.insert(0, os.getcwd())

from sven.transaction import UpgradeTransaction
from sven.db.models import Package


class FakeLocalDB:
    def __init__(self, pkgs):
        self._pkgs = {p.name: p for p in pkgs}

    def list_installed(self):
        return list(self._pkgs.keys())

    def get(self, name):
        return self._pkgs.get(name)


class FakeSyncDB:
    """No entries — every installed package looks AUR-origin to resolve()."""
    def get(self, name):
        return None


class FakeAURDB:
    def __init__(self):
        self.called_with = None

    def info_multi(self, names):
        self.called_with = list(names)
        return []


class TestSkipAur(unittest.TestCase):

    def _make_tx(self, installed_pkgs):
        tx = UpgradeTransaction(explicit=False, verbose=False)
        tx.local_db = FakeLocalDB(installed_pkgs)
        tx.sync_db = FakeSyncDB()
        tx.aur_db = FakeAURDB()
        return tx

    def test_skip_aur_never_calls_aur_db(self):
        tx = self._make_tx([Package(name="yay-bin", version="1.0", origin="aur")])
        tx.resolve(skip_aur=True)
        self.assertIsNone(tx.aur_db.called_with, "skip_aur=True must not touch the AUR RPC at all")

    def test_skip_aur_reports_honest_skipped_count(self):
        tx = self._make_tx([
            Package(name="yay-bin", version="1.0", origin="aur"),
            Package(name="paru-bin", version="1.0", origin="aur"),
        ])
        tx.resolve(skip_aur=True)
        self.assertEqual(tx.skipped_aur_count, 2)

    def test_without_skip_aur_aur_db_is_still_called(self):
        tx = self._make_tx([Package(name="yay-bin", version="1.0", origin="aur")])
        tx.resolve(skip_aur=False)
        self.assertEqual(tx.aur_db.called_with, ["yay-bin"])
        self.assertEqual(tx.skipped_aur_count, 0)


if __name__ == "__main__":
    unittest.main()
