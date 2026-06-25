# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_adoption.py
# ============================================================
import sys
import os
import unittest

sys.path.insert(0, os.getcwd())

from sven.version_probe import detect_version, is_present, generic_probe
from sven.db.models import Package


class TestVersionProbe(unittest.TestCase):

    def test_known_present_tool_is_verified(self):
        # bash is virtually guaranteed present in any test environment
        version, verified = detect_version("bash")
        self.assertTrue(verified)
        self.assertRegex(version, r"^\d+\.\d+")

    def test_no_version_source_packages_are_honestly_unverified(self):
        for name in ("filesystem", "ca-certificates", "linux-firmware"):
            version, verified = detect_version(name)
            self.assertFalse(verified, f"{name} should not claim a verified version")

    def test_derived_package_inherits_parent_status(self):
        # glibc-locales derives from glibc — if glibc resolves, so should this
        glibc_v, glibc_ok = detect_version("glibc")
        locales_v, locales_ok = detect_version("glibc-locales")
        if glibc_ok:
            self.assertTrue(locales_ok)
            self.assertEqual(glibc_v, locales_v)

    def test_unknown_random_package_does_not_crash(self):
        version, verified = detect_version("definitely-not-a-real-package-xyz123")
        self.assertEqual(version, "unknown")
        self.assertFalse(verified)

    def test_is_present_handles_multi_binary_packages(self):
        # coreutils/glibc are not binaries themselves — must resolve via
        # their representative binary (ls / ldd) rather than literal name
        self.assertTrue(is_present("coreutils"))
        self.assertTrue(is_present("glibc"))

    def test_generic_probe_never_raises_on_missing_binary(self):
        self.assertIsNone(generic_probe("not-a-real-binary-xyz123"))


class TestBlfsMatching(unittest.TestCase):
    """
    Confirms a single weak/generic signal alone can never trigger adoption —
    this is the false-positive fix for the original loose-threshold bug.
    """

    def setUp(self):
        import scripts.adopt_blfs as ab
        self.ab = ab

    def test_single_weak_signal_rejected(self):
        class FakeSyncDB:
            def all_packages(self):
                return [Package(name="coincidental-name", version="1.0", provides=[])]

        class FakeLocalDB:
            def list_installed(self):
                return []

        system_libs = {"libcoincidental-name.so": "/usr/lib/libcoincidental-name.so"}
        result = self.ab.match_packages(
            FakeSyncDB(), FakeLocalDB(),
            system_libs, {}, {}, {}, min_score=5,
        )
        self.assertEqual(result, [], "a single lib-prefix match alone must not be adopted")

    def test_binary_match_alone_is_sufficient(self):
        class FakeSyncDB:
            def all_packages(self):
                return [Package(name="realtool", version="1.0", provides=[])]

        class FakeLocalDB:
            def list_installed(self):
                return []

        system_bins = {"realtool": "/usr/bin/realtool"}
        result = self.ab.match_packages(
            FakeSyncDB(), FakeLocalDB(),
            {}, system_bins, {}, {}, min_score=5,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0].name, "realtool")

    def test_two_weak_signals_combine_to_adopt(self):
        class FakeSyncDB:
            def all_packages(self):
                return [Package(name="multisig", version="1.0", provides=["libmultisig.so"])]

        class FakeLocalDB:
            def list_installed(self):
                return []

        system_libs = {"libmultisig.so": "/usr/lib/libmultisig.so"}
        system_pcs = {"multisig": "/usr/lib/pkgconfig/multisig.pc"}
        result = self.ab.match_packages(
            FakeSyncDB(), FakeLocalDB(),
            system_libs, {}, system_pcs, {}, min_score=5,
        )
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
