# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_status_banner.py
# ============================================================
import sys
import os
import unittest

sys.path.insert(0, os.getcwd())

from sven.db.local_db import LocalDB
from sven.db.models import Package


class FakeSyncDB:
    """Simulates SyncDB in either a never-synced or loaded state."""
    def __init__(self, loaded=True, packages=None):
        self._loaded = loaded
        self._packages = packages or {}

    def _ensure_loaded(self):
        if not self._loaded:
            from sven.exceptions import DatabaseError
            raise DatabaseError("No sync DBs found")

    def get(self, name):
        return self._packages.get(name)


class TestCountUpgradable(unittest.TestCase):

    def setUp(self):
        self.db = LocalDB(
            db_path="/tmp/test_status_banner_db",
            lock_path="/tmp/test_status_banner_db.lock",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree("/tmp/test_status_banner_db", ignore_errors=True)
        try:
            os.remove("/tmp/test_status_banner_db.lock")
        except OSError:
            pass

    def test_never_synced_returns_none_not_zero(self):
        """
        'Never synced' and 'confirmed zero upgrades' are different facts.
        Collapsing them into the same 0 is the exact misleading-confidence
        bug fixed in sync.py earlier — must not regress here either.
        """
        self.db.register(Package(name="bash", version="5.0", version_verified=True), files=[])
        result = self.db.count_upgradable(sync_db=FakeSyncDB(loaded=False))
        self.assertIsNone(result, "never-synced state must report None, not 0")

    def test_confirmed_zero_upgrades_is_distinguishable(self):
        self.db.register(Package(name="bash", version="5.0", version_verified=True), files=[])
        fake = FakeSyncDB(loaded=True, packages={"bash": Package(name="bash", version="5.0")})
        result = self.db.count_upgradable(sync_db=fake)
        self.assertEqual(result, 0)
        self.assertIsNotNone(result)

    def test_real_upgrade_is_counted(self):
        self.db.register(Package(name="bash", version="5.0", version_verified=True), files=[])
        fake = FakeSyncDB(loaded=True, packages={"bash": Package(name="bash", version="5.2")})
        result = self.db.count_upgradable(sync_db=fake)
        self.assertEqual(result, 1)

    def test_unverified_version_skipped_not_compared(self):
        self.db.register(Package(name="filesystem", version="unknown", version_verified=False), files=[])
        fake = FakeSyncDB(loaded=True, packages={"filesystem": Package(name="filesystem", version="2024.01.01")})
        result = self.db.count_upgradable(sync_db=fake)
        self.assertEqual(result, 0, "unverified versions must not be compared at all")

    def test_aur_packages_skipped(self):
        self.db.register(Package(name="some-aur-pkg", version="1.0", origin="aur", version_verified=True), files=[])
        fake = FakeSyncDB(loaded=True, packages={"some-aur-pkg": Package(name="some-aur-pkg", version="2.0")})
        result = self.db.count_upgradable(sync_db=fake)
        self.assertEqual(result, 0, "AUR packages need network to check — must be skipped, not silently wrong")


if __name__ == "__main__":
    unittest.main()
