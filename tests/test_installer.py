# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_installer.py — tests for Phase 5 installer
# ============================================================

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from sven.installer.extractor import Extractor
from sven.installer.hooks import HookRunner
from sven.installer.lib_checker import LibChecker
from sven.installer.rollback import RollbackManager
from sven.exceptions import (
    ExtractionError,
    MissingLibraryError,
    SnapshotNotFoundError,
)


class TestExtractor(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.extractor = Extractor(install_root=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_missing_archive_raises(self):
        """Should raise ExtractionError if file does not exist."""
        with self.assertRaises(ExtractionError):
            self.extractor.extract(os.path.join(self.tmpdir, "missing.pkg.tar.zst"))

    # A real test of extract() would require a mock .pkg.tar.zst file, 
    # which is quite heavy for unit testing. We are verifying the 
    # structure and error raise exist.


class TestLibChecker(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.lib_path = os.path.join(self.tmpdir, "lib")
        os.makedirs(self.lib_path)
        self.checker = LibChecker(custom_lib_paths=[self.lib_path])

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_lib_exists(self):
        """Should pass if required SO exists."""
        # Create fake SO
        with open(os.path.join(self.lib_path, "libfoo.so.2"), "w") as f:
            f.write("fake")

        result = self.checker.check_package("my-app", ["libfoo.so.2"])
        self.assertTrue(result)

    def test_lib_symlink_fallback(self):
        """Should pass if generic un-versioned SO exists."""
        # We only have libfoo.so, but package asked for libfoo.so.2
        with open(os.path.join(self.lib_path, "libfoo.so"), "w") as f:
            f.write("fake")

        result = self.checker.check_package("my-app", ["libfoo.so.2"])
        self.assertTrue(result)

    def test_lib_missing_raises(self):
        """Should raise MissingLibraryError if not found."""
        with self.assertRaises(MissingLibraryError):
            self.checker.check_package("my-app", ["libmissing.so"])


class TestHooks(unittest.TestCase):
    @patch("sven.installer.hooks.get_config")
    def test_systemctl_translation_sysvinit(self, mock_config):
        """Should translate systemctl commands to init.d/rc-update."""
        mock_cfg = MagicMock()
        mock_cfg.init_system = "sysvinit"
        mock_config.return_value = mock_cfg

        runner = HookRunner("pkg", "dummy.install")
        
        script = "systemctl enable sshd.service\nsystemctl start sshd\n"
        result = runner._translate_systemctl(script)
        
        self.assertIn("rc-update add sshd default", result)
        self.assertIn("/etc/init.d/sshd start", result)

    @patch("sven.installer.hooks.get_config")
    def test_systemctl_translation_systemd(self, mock_config):
        """Should NOT translate if init_system is systemd."""
        mock_cfg = MagicMock()
        mock_cfg.init_system = "systemd"
        mock_config.return_value = mock_cfg

        runner = HookRunner("pkg", "dummy.install")
        
        script = "systemctl start sshd"
        result = runner._translate_systemctl(script)
        
        self.assertEqual(script, result)

    @patch("sven.installer.hooks.get_config")
    def test_daemon_reload_skipped(self, mock_config):
        """Should map daemon-reload to bash colon (noop)."""
        mock_cfg = MagicMock()
        mock_cfg.init_system = "sysvinit"
        mock_config.return_value = mock_cfg

        runner = HookRunner("pkg", "dummy.install")
        
        script = "systemctl daemon-reload"
        result = runner._translate_systemctl(script)
        
        self.assertEqual(":", result.strip())


class TestRollbackManager(unittest.TestCase):
    @patch("sven.installer.rollback.LocalDB")
    def setUp(self, mock_local_db):
        self.tmpdir = tempfile.mkdtemp()
        self.snap_dir = os.path.join(self.tmpdir, "snapshots")
        
        self.mock_db = MagicMock()
        mock_local_db.return_value = self.mock_db
        
        with patch("sven.installer.rollback.get_config") as mock_cfg:
            mock_cfg.return_value.rooted.side_effect = lambda x: f"{self.tmpdir}{x}"
            self.manager = RollbackManager(snapshot_dir="/snapshots")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_create_snapshot(self):
        """Should create manifest and changed_files dir."""
        self.mock_db.list_installed.return_value = ["foo"]
        self.mock_db.get_files.return_value = []
        
        mock_pkg = MagicMock()
        mock_pkg.version = "1.0"
        self.mock_db.get.return_value = mock_pkg
        
        snap_id = self.manager.create_snapshot(["foo"])
        
        snap_path = os.path.join(self.snap_dir, snap_id)
        self.assertTrue(os.path.exists(snap_path))
        self.assertTrue(os.path.exists(os.path.join(snap_path, "manifest.json")))
        self.assertTrue(os.path.exists(os.path.join(snap_path, "changed_files")))

    def test_snapshot_not_found_raises(self):
        """Restoring missing snapshot throws error."""
        with self.assertRaises(SnapshotNotFoundError):
            self.manager.restore("snapshot-fake")


if __name__ == "__main__":
    unittest.main()
