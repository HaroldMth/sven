# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_fail_fast_conflicts.py
# ============================================================
"""
Reported live: an upgrade downloaded and SHA256-verified 566 cached
packages, then failed at "Install · 4/6 · Safety checks" with a package
conflict (zlib-ng-compat conflicts with zlib) that only needed metadata
already available before any download started. Confirmed against real
Arch package data that the conflict itself is legitimate (zlib-ng-compat
declares conflicts=zlib without a replaces=zlib, so pacman would refuse
the same combination) — the bug is purely that it was caught after
burning time/bandwidth on a doomed transaction, not before.
"""
import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.getcwd())

from sven.transaction import InstallTransaction
from sven.db.models import Package
from sven.exceptions import DependencyConflictError


class FakeLocalDB:
    def __init__(self, pkgs):
        self._pkgs = {p.name: p for p in pkgs}

    def list_installed(self):
        return list(self._pkgs.keys())

    def all_packages(self):
        return list(self._pkgs.values())

    def get(self, name):
        return self._pkgs.get(name)

    def acquire_lock(self):
        return True

    def release_lock(self):
        pass


class TestFailFastConflicts(unittest.TestCase):

    def test_conflict_raised_before_any_download(self):
        tx = InstallTransaction(explicit=True, verbose=False)
        tx.local_db = FakeLocalDB([Package(name="zlib", version="1.3.1-1")])

        conflicting_pkg = Package(
            name="zlib-ng-compat",
            version="2.3.3-1",
            conflicts=["zlib"],
            provides=["zlib", "libz.so"],
        )
        tx._resolved_pkgs = [conflicting_pkg]
        tx._install_target_names = frozenset(["zlib-ng-compat"])

        with patch("sven.transaction.Fetcher") as mock_fetcher_cls:
            with self.assertRaises(DependencyConflictError):
                tx._execute_core([], _use_resolved=True)

            mock_fetcher_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
