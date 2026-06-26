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

    def test_legacy_blfs_placeholder_excluded_even_when_verified_true(self):
        """
        Legacy entries registered before version_verified existed default to
        True even though their version string is an old "BLFS-x.y" placeholder,
        not a real version. Comparing that against a real sync version with
        vercmp produces a meaningless result and silently inflates the count.
        """
        legacy_pkg = Package(name="systemd-libs", version="BLFS-260.1-2", origin="local")
        self.assertTrue(legacy_pkg.version_verified, "default must be True to reproduce the real bug")
        self.db.register(legacy_pkg, files=[])
        fake = FakeSyncDB(loaded=True, packages={"systemd-libs": Package(name="systemd-libs", version="260.1-2")})
        result = self.db.count_upgradable(sync_db=fake)
        self.assertEqual(result, 0, "BLFS-/LFS- placeholder versions must never be compared, verified flag or not")


class TestSyncStatusFallback(unittest.TestCase):
    """
    .sync_state.json is new — a pre-existing system synced under an older
    Sven build has real, loadable .db files with no timestamp marker at all.
    The freshness label must not claim "never synced" in that case; doing so
    directly contradicts a banner that simultaneously shows a real upgrade
    count computed from that same "nonexistent" data.
    """

    def setUp(self):
        import shutil
        shutil.rmtree("/tmp/test_sync_fallback", ignore_errors=True)
        os.makedirs("/tmp/test_sync_fallback/sync")

    def tearDown(self):
        import shutil
        shutil.rmtree("/tmp/test_sync_fallback", ignore_errors=True)

    def test_no_state_file_but_real_db_present_is_not_never_synced(self):
        from pathlib import Path
        from sven.db.sync_db import SyncDB
        from sven.ui.output import _sync_status

        open("/tmp/test_sync_fallback/sync/core.db", "w").close()

        orig_init = SyncDB.__init__
        def patched_init(self, *a, **kw):
            orig_init(self, *a, **kw)
            self.db_path = Path("/tmp/test_sync_fallback/sync")
        SyncDB.__init__ = patched_init
        SyncDB.read_sync_state = staticmethod(lambda db_path=None: None)

        try:
            _, label = _sync_status()
            self.assertNotEqual(label, "never synced")
        finally:
            SyncDB.__init__ = orig_init

    def test_no_state_file_and_no_db_is_genuinely_never_synced(self):
        from pathlib import Path
        from sven.db.sync_db import SyncDB
        from sven.ui.output import _sync_status

        orig_init = SyncDB.__init__
        def patched_init(self, *a, **kw):
            orig_init(self, *a, **kw)
            self.db_path = Path("/tmp/test_sync_fallback/sync")  # empty dir, no .db files
        SyncDB.__init__ = patched_init
        SyncDB.read_sync_state = staticmethod(lambda db_path=None: None)

        try:
            _, label = _sync_status()
            self.assertEqual(label, "never synced")
        finally:
            SyncDB.__init__ = orig_init


if __name__ == "__main__":
    unittest.main()
