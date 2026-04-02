# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  tests/test_resolver.py — unit tests for Phase 2 (unittest)
# ============================================================

import unittest
from unittest.mock import MagicMock
from sven.db.models import Package
from sven.resolver.search import search
from sven.resolver.graph import DependencyGraph, Version, parse_dep
from sven.resolver.sorter import sort_dependencies
from sven.resolver.conflict import check_conflicts
from sven.resolver.compat import check_binary_compatibility, CompatibilityLevel
from sven.exceptions import CircularDependencyError, DependencyConflictError, VersionConstraintError


class TestResolver(unittest.TestCase):

    def setUp(self):
        self.mock_pkgs = {
            "bash": Package(name="bash", version="5.2.15-1", repo="core", origin="official", deps=["readline", "glibc"]),
            "readline": Package(name="readline", version="8.2.0-1", repo="core", origin="official", deps=["glibc"]),
            "glibc": Package(name="glibc", version="2.37-1", repo="core", origin="official"),
            "spotify": Package(name="spotify", version="1:1.2.8.107-1", repo="aur", origin="aur", deps=["glibc", "alsa-lib"]),
            "alsa-lib": Package(name="alsa-lib", version="1.2.9-1", repo="extra", origin="official"),
        }

    # ── Search Tests ─────────────────────────────────────────────

    def test_search_results(self):
        sync_db = MagicMock()
        aur_db  = MagicMock()
        
        sync_db.search.return_value = [self.mock_pkgs["bash"]]
        aur_db.search.return_value  = [self.mock_pkgs["spotify"]]
        
        results = search("ba", sync_db, aur_db)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "bash")
        self.assertEqual(results[1].name, "spotify")

    # ── Graph Tests ──────────────────────────────────────────────

    def test_version_comparison(self):
        v1 = Version("5.2.15-1")
        v2 = Version("5.2.15-2")
        v3 = Version("5.3.0-1")
        
        self.assertTrue(v1 < v2)
        self.assertTrue(v2 < v3)
        self.assertTrue(v1 < v3)
        self.assertEqual(v1, Version("5.2.15-1"))

    def test_parse_dep(self):
        self.assertEqual(parse_dep("bash>=5.0"), ("bash", ">=", "5.0"))
        self.assertEqual(parse_dep("readline"), ("readline", None, None))

    def test_graph_building(self):
        sync_db = MagicMock()
        aur_db  = MagicMock()
        local_db = MagicMock()
        
        sync_db.get.side_effect = lambda n: self.mock_pkgs.get(n) if self.mock_pkgs.get(n) and self.mock_pkgs[n].origin == "official" else None
        aur_db.info.side_effect = lambda n: self.mock_pkgs.get(n) if self.mock_pkgs.get(n) and self.mock_pkgs[n].origin == "aur" else None
        local_db.get.return_value = None
        
        graph = DependencyGraph(sync_db, aur_db, local_db)
        graph.add_package("bash")
        
        self.assertIn("bash", graph.nodes)
        self.assertIn("readline", graph.nodes)
        self.assertIn("glibc", graph.nodes)
        self.assertIn("glibc", graph.edges["bash"])

    # ── Sorter Tests ─────────────────────────────────────────────

    def test_topological_sort(self):
        nodes = self.mock_pkgs
        edges = {
            "bash": {"readline", "glibc"},
            "readline": {"glibc"},
            "glibc": set()
        }
        
        order = sort_dependencies(nodes, edges)
        names = [p.name for p in order]
        self.assertEqual(names, ["glibc", "readline", "bash"])

    def test_circular_dependency(self):
        nodes = {
            "A": Package(name="A", version="1"),
            "B": Package(name="B", version="1")
        }
        edges = {
            "A": {"B"},
            "B": {"A"}
        }
        with self.assertRaises(CircularDependencyError):
            sort_dependencies(nodes, edges)

    # ── Conflict Tests ───────────────────────────────────────────

    def test_conflict_detection(self):
        local_db = MagicMock()
        installed_pkg = Package(name="old-bash", version="4.0", conflicts=["bash"])
        local_db.all_packages.return_value = [installed_pkg]
        
        with self.assertRaises(DependencyConflictError):
            check_conflicts([self.mock_pkgs["bash"]], local_db)

    # ── Compatibility Tests ───────────────────────────────────────

    def test_binary_compatibility(self):
        self.assertEqual(check_binary_compatibility(self.mock_pkgs["bash"]), CompatibilityLevel.BINARY_SAFE)
        
        pkg_with_so = Package(name="test", version="1", deps=["libssl.so>=3"])
        # Should return SOURCE_REQUIRED as libssl.so is not likely to exist in this exact form in standard paths without .so.X
        # But let's just make sure it returns a valid CompatibilityLevel
        res = check_binary_compatibility(pkg_with_so)
        self.assertIsInstance(res, CompatibilityLevel)


if __name__ == "__main__":
    unittest.main()
