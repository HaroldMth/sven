# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_downloader.py — unit tests for Phase 3
# ============================================================

import os
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from sven.db.models import Package
from sven.downloader.mirror import MirrorManager
from sven.downloader.fetcher import Fetcher
from sven.downloader.checksum import verify_checksum
from sven.downloader.pkgbuild_fetcher import PKGBUILDFetcher
from sven.exceptions import (
    ChecksumMismatchError,
    MirrorError,
    DownloadError,
)


class TestMirrorManager(unittest.TestCase):

    def test_default_mirror(self):
        """When no cached mirrors exist, should return the default mirror."""
        mm = MirrorManager(cache_path="/tmp/_sven_test_nonexistent_mirrors.json")
        self.assertIn("archlinux", mm.current)

    def test_next_mirror_exhausted(self):
        """Should raise MirrorError when all mirrors are exhausted."""
        mm = MirrorManager(cache_path="/tmp/_sven_test_nonexistent_mirrors.json")
        mm._mirrors = [
            {"url": "https://mirror1.example.com", "country": "US", "score": 1, "ping_ms": 10},
            {"url": "https://mirror2.example.com", "country": "DE", "score": 2, "ping_ms": 20},
        ]
        mm._current_index = 0

        # Advance to mirror2
        url = mm.next_mirror()
        self.assertEqual(url, "https://mirror2.example.com")

        # No more mirrors
        with self.assertRaises(MirrorError):
            mm.next_mirror()

    def test_reset(self):
        """Reset should bring us back to the first mirror."""
        mm = MirrorManager(cache_path="/tmp/_sven_test_nonexistent_mirrors.json")
        mm._mirrors = [
            {"url": "https://mirror1.example.com", "country": "US", "score": 1, "ping_ms": 10},
            {"url": "https://mirror2.example.com", "country": "DE", "score": 2, "ping_ms": 20},
        ]
        mm._current_index = 1
        mm.reset()
        self.assertEqual(mm._current_index, 0)
        self.assertEqual(mm.current, "https://mirror1.example.com")


class TestChecksum(unittest.TestCase):

    def test_valid_checksum(self):
        """SHA256 should pass for correct content."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkg") as f:
            f.write(b"hello sven")
            tmp_path = f.name

        expected = hashlib.sha256(b"hello sven").hexdigest()
        try:
            result = verify_checksum(tmp_path, expected)
            self.assertTrue(result)
        finally:
            os.unlink(tmp_path)

    def test_invalid_checksum(self):
        """SHA256 should raise ChecksumMismatchError for wrong content."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkg") as f:
            f.write(b"hello sven")
            tmp_path = f.name

        try:
            with self.assertRaises(ChecksumMismatchError):
                verify_checksum(tmp_path, "0000000000000000000000000000000000000000000000000000000000000000")
        finally:
            os.unlink(tmp_path)

    def test_missing_file(self):
        """Should raise ChecksumMismatchError for missing file."""
        with self.assertRaises(ChecksumMismatchError):
            verify_checksum("/tmp/_sven_nonexistent_file.pkg", "abc")


class TestFetcher(unittest.TestCase):

    def test_cached_package_skipped(self):
        """Already cached packages should be skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mm = MagicMock()
            mm.current = "https://mirror.example.com/archlinux"

            fetcher = Fetcher(mirror_manager=mm, cache_dir=tmpdir, parallel=1)

            # Create a fake cached file
            pkg = Package(name="bash", version="5.2-1", repo="core", filename="bash-5.2-1-x86_64.pkg.tar.zst")
            cached_file = Path(tmpdir) / pkg.filename
            cached_file.write_text("fake cached content")

            results = fetcher.download_packages([pkg])
            self.assertIn("bash", results)
            self.assertEqual(results["bash"], cached_file)


class TestPKGBUILDFetcher(unittest.TestCase):

    @patch("subprocess.run")
    def test_git_clone(self, mock_run):
        """Should call git clone for a new package."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "spotify"

            def fake_clone(*args, **kwargs):
                # Simulate git clone by creating the directory + PKGBUILD
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "PKGBUILD").write_text("# fake")
                return MagicMock(returncode=0, stderr="", stdout="")

            mock_run.side_effect = fake_clone

            fetcher = PKGBUILDFetcher(build_dir=tmpdir)
            result = fetcher.fetch_aur("spotify")

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            self.assertEqual(call_args[0], "git")
            self.assertIn("clone", call_args)
            self.assertIn("spotify", call_args[-1])
            self.assertEqual(result, dest)


if __name__ == "__main__":
    unittest.main()
