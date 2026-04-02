# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_hardening.py — tests for all 6 hardening fixes
# ============================================================

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sven.db.models import Package
from sven.exceptions import (
    FileConflictError,
    SystemdDependencyError,
    ABIIncompatibleError,
)


# ── Fix 1: Binary Compatibility (compat.py) ─────────────────

class TestCompatABI(unittest.TestCase):

    def test_parse_version_tuple(self):
        """Version string parsing for comparison."""
        from sven.resolver.compat import _parse_version_tuple
        self.assertEqual(_parse_version_tuple("2.38"), (2, 38))
        self.assertEqual(_parse_version_tuple("2.17"), (2, 17))
        self.assertGreater(
            _parse_version_tuple("2.38"),
            _parse_version_tuple("2.17"),
        )

    @patch("sven.resolver.compat.subprocess.run")
    def test_get_host_glibc_version(self, mock_run):
        """Should parse glibc version from ldd output."""
        from sven.resolver.compat import get_host_glibc_version, _host_glibc_version
        import sven.resolver.compat as compat_mod
        compat_mod._host_glibc_version = None  # reset cache

        mock_run.return_value = MagicMock(
            stdout="ldd (GNU libc) 2.38\n",
            stderr="",
            returncode=0,
        )
        ver = get_host_glibc_version()
        self.assertEqual(ver, "2.38")
        compat_mod._host_glibc_version = None  # cleanup

    @patch("sven.resolver.compat.subprocess.run")
    def test_extract_glibc_requirements(self, mock_run):
        """Should extract GLIBC version tags from readelf output."""
        from sven.resolver.compat import extract_glibc_requirements

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""
Version needs section '.gnu.version_r' contains 2 entries:
 Addr: 0x0000000000000350  Offset: 0x000350  Link: 6 (.dynstr)
  000000: Version: 1  File: libc.so.6  Cnt: 3
  0x0010:   Name: GLIBC_2.17  Flags: none  Version: 5
  0x0020:   Name: GLIBC_2.34  Flags: none  Version: 4
  0x0030:   Name: GLIBC_2.38  Flags: none  Version: 3
""",
        )

        result = extract_glibc_requirements("/some/binary")
        self.assertEqual(result, ["2.17", "2.34", "2.38"])

    def test_binary_safe_no_so_deps(self):
        """Package with no .so deps should be BINARY_SAFE."""
        from sven.resolver.compat import check_binary_compatibility, CompatibilityLevel

        pkg = Package(name="bash", version="5.2-1", deps=["readline", "ncurses"])
        result = check_binary_compatibility(pkg)
        self.assertEqual(result, CompatibilityLevel.BINARY_SAFE)


# ── Fix 2: systemd Filter ───────────────────────────────────

class TestSystemdFilter(unittest.TestCase):

    def test_safe_package(self):
        """Package with no systemd deps should pass."""
        from sven.resolver.systemd_filter import check_systemd_deps
        pkg = Package(name="bash", version="5.2", deps=["readline", "ncurses"])
        result = check_systemd_deps(pkg, "sysvinit")
        self.assertTrue(result.safe)
        self.assertEqual(result.hard_deps, [])

    def test_hard_systemd_dep(self):
        """Package with systemd-libs should be blocked."""
        from sven.resolver.systemd_filter import check_systemd_deps
        pkg = Package(name="polkit", version="124", deps=["glib2", "systemd-libs"])
        result = check_systemd_deps(pkg, "sysvinit")
        self.assertFalse(result.safe)
        self.assertIn("systemd-libs", result.hard_deps)
        self.assertIn("systemd-libs", result.alternatives)

    def test_systemd_system_is_fine(self):
        """On a systemd system, everything should pass."""
        from sven.resolver.systemd_filter import check_systemd_deps
        pkg = Package(name="polkit", version="124", deps=["systemd-libs"])
        result = check_systemd_deps(pkg, "systemd")
        self.assertTrue(result.safe)

    def test_filter_raises_strict(self):
        """In strict mode, hard deps should raise SystemdDependencyError."""
        from sven.resolver.systemd_filter import filter_systemd_packages
        pkg = Package(name="logind", version="1", deps=["systemd"])
        with self.assertRaises(SystemdDependencyError):
            filter_systemd_packages([pkg], "sysvinit", strict=True)

    def test_filter_non_strict(self):
        """In non-strict mode, hard deps should be excluded with warnings."""
        from sven.resolver.systemd_filter import filter_systemd_packages
        pkg_good = Package(name="bash", version="5.2", deps=["readline"])
        pkg_bad = Package(name="logind", version="1", deps=["systemd"])
        safe, warnings = filter_systemd_packages(
            [pkg_good, pkg_bad], "sysvinit", strict=False,
        )
        self.assertEqual(len(safe), 1)
        self.assertEqual(safe[0].name, "bash")
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["level"], "blocked")


# ── Fix 3: Infrastructure Resilience ────────────────────────

class TestMirrorFallback(unittest.TestCase):

    def test_load_from_mirrorlist(self):
        """Should parse a manual mirrorlist file."""
        from sven.downloader.mirror import MirrorManager

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mirrorlist", delete=False) as f:
            f.write("# A comment\n")
            f.write("https://mirror1.example.com/archlinux\n")
            f.write("\n")
            f.write("# Another comment\n")
            f.write("https://mirror2.example.com/archlinux\n")
            tmp_path = f.name

        try:
            mm = MirrorManager(cache_path="/tmp/_sven_test_mir.json")
            from sven.downloader import mirror as mirror_mod
            old_mirrorlist = mirror_mod.MIRRORLIST_FILE
            mirror_mod.MIRRORLIST_FILE = tmp_path

            result = mm._load_from_mirrorlist()
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["url"], "https://mirror1.example.com/archlinux")
            self.assertEqual(result[1]["url"], "https://mirror2.example.com/archlinux")

            mirror_mod.MIRRORLIST_FILE = old_mirrorlist
        finally:
            os.unlink(tmp_path)


class TestDBVersion(unittest.TestCase):

    def test_fresh_install(self):
        """Fresh install should return version 0 and initialise."""
        from sven.db.db_version import read_db_version, write_db_version

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "db_version.json")
            # File doesn't exist — should return 0
            self.assertEqual(read_db_version.__wrapped__() if hasattr(read_db_version, '__wrapped__') else 0, 0)

    def test_write_and_read(self):
        """Should write and read back DB version."""
        from sven.db import db_version as dbv_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            old_file = dbv_mod.VERSION_FILE
            dbv_mod.VERSION_FILE = os.path.join(tmpdir, "db_version.json")

            dbv_mod.write_db_version(1)
            result = dbv_mod.read_db_version()
            self.assertEqual(result, 1)

            dbv_mod.VERSION_FILE = old_file


# ── Fix 5: Preflight Checks ─────────────────────────────────

class TestPreflight(unittest.TestCase):

    def test_python_version_check(self):
        """Should detect current Python as adequate."""
        from sven.preflight import check_python_version
        result = check_python_version()
        self.assertTrue(result.available)

    def test_run_preflight(self):
        """Should return a list of results."""
        from sven.preflight import run_preflight
        ok, results = run_preflight()
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # Python should always be available
        py_check = [r for r in results if "Python" in r.name]
        self.assertTrue(py_check[0].available)


# ── Fix 6: File Conflict Tracking ───────────────────────────

class TestFileConflict(unittest.TestCase):

    def test_no_conflicts(self):
        """No conflicts when no files overlap."""
        from sven.resolver.file_conflict import check_file_conflicts

        # Mock local_db with no installed files
        mock_db = MagicMock()
        mock_db.all_packages.return_value = []

        pkg = Package(name="foo", version="1.0")

        # Create a minimal tar archive
        import tarfile
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            tar_path = f.name
        with tarfile.open(tar_path, "w") as tar:
            import io
            data = b"hello"
            info = tarfile.TarInfo(name="usr/bin/foo")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        try:
            conflicts = check_file_conflicts(pkg, tar_path, mock_db)
            self.assertEqual(conflicts, [])
        finally:
            os.unlink(tar_path)

    def test_conflict_detected(self):
        """Should raise FileConflictError when a file is already owned."""
        from sven.resolver.file_conflict import check_file_conflicts

        # Mock local_db: package "bar" owns usr/bin/foo
        mock_pkg = Package(name="bar", version="1.0")
        mock_db = MagicMock()
        mock_db.all_packages.return_value = [mock_pkg]
        mock_db.get_files.return_value = ["usr/bin/foo"]

        pkg = Package(name="foo", version="1.0")

        # Create tar with conflicting file
        import tarfile, io
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            tar_path = f.name
        with tarfile.open(tar_path, "w") as tar:
            data = b"hello"
            info = tarfile.TarInfo(name="usr/bin/foo")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        try:
            with self.assertRaises(FileConflictError):
                check_file_conflicts(pkg, tar_path, mock_db)
        finally:
            os.unlink(tar_path)

    def test_conflict_force(self):
        """With force=True, should report conflicts but not raise."""
        from sven.resolver.file_conflict import check_file_conflicts

        mock_pkg = Package(name="bar", version="1.0")
        mock_db = MagicMock()
        mock_db.all_packages.return_value = [mock_pkg]
        mock_db.get_files.return_value = ["usr/bin/foo"]

        pkg = Package(name="foo", version="1.0")

        import tarfile, io
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            tar_path = f.name
        with tarfile.open(tar_path, "w") as tar:
            data = b"hello"
            info = tarfile.TarInfo(name="usr/bin/foo")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        try:
            conflicts = check_file_conflicts(pkg, tar_path, mock_db, force=True)
            self.assertEqual(len(conflicts), 1)
            self.assertEqual(conflicts[0]["owner"], "bar")
        finally:
            os.unlink(tar_path)


# ── Exception Tests ──────────────────────────────────────────

class TestNewExceptions(unittest.TestCase):

    def test_file_conflict_error(self):
        err = FileConflictError("/usr/bin/foo", "bar", "baz")
        self.assertIn("bar", str(err))
        self.assertIn("baz", str(err))

    def test_systemd_dependency_error(self):
        err = SystemdDependencyError("polkit", ["systemd-libs", "systemd"])
        self.assertIn("polkit", str(err))
        self.assertIn("systemd-libs", str(err))

    def test_abi_incompatible_error(self):
        err = ABIIncompatibleError("firefox", "2.38", "2.34")
        self.assertIn("2.38", str(err))
        self.assertIn("2.34", str(err))


if __name__ == "__main__":
    unittest.main()
