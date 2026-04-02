# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  resolver/graph.py — dependency graph builder
# ============================================================

import re
from typing import Optional, Set, Dict, List
from ..db.models import Package
from ..db.sync_db import SyncDB
from ..db.aur_db import AURDB
from ..db.local_db import LocalDB
from ..exceptions import DependencyNotFoundError, VersionConstraintError


class Version:
    """
    Simple Arch-compatible version comparison.
    Handles pkgver-pkgrel format.
    """
    def __init__(self, v_str: str):
        self.v_str = v_str
        # Split into components for comparison
        # This is a simplified version of alpm_pkg_vercmp
        self.parts = re.split(r'[^a-zA-Z0-9]+', v_str)

    def __lt__(self, other: 'Version'):
        return self._compare(other) < 0

    def __le__(self, other: 'Version'):
        return self._compare(other) <= 0

    def __gt__(self, other: 'Version'):
        return self._compare(other) > 0

    def __ge__(self, other: 'Version'):
        return self._compare(other) >= 0

    def __eq__(self, other: 'Version'):
        return self._compare(other) == 0

    def _compare(self, other: 'Version') -> int:
        for p1, p2 in zip(self.parts, other.parts):
            if p1.isdigit() and p2.isdigit():
                n1, n2 = int(p1), int(p2)
                if n1 < n2: return -1
                if n1 > n2: return 1
            else:
                if p1 < p2: return -1
                if p1 > p2: return 1
        
        if len(self.parts) < len(other.parts): return -1
        if len(self.parts) > len(other.parts): return 1
        return 0


def parse_dep(dep_str: str) -> tuple[str, Optional[str], Optional[str]]:
    """
    Parse a dependency string like "bash>=5.0"
    Returns (name, operator, version)
    """
    match = re.match(r'^([^<>=]+)([<>=]+)(.+)$', dep_str)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return dep_str, None, None


class DependencyGraph:
    """
    Builds a Directed Acyclic Graph of package dependencies.
    """

    def __init__(
        self,
        sync_db: SyncDB,
        aur_db: AURDB,
        local_db: LocalDB,
        include_makedeps: bool = False
    ):
        self.sync_db = sync_db
        self.aur_db  = aur_db
        self.local_db = local_db
        self.include_makedeps = include_makedeps

        # Node map: name -> Package
        self.nodes: Dict[str, Package] = {}
        # Edge map: name -> set of dependency names
        self.edges: Dict[str, Set[str]] = {}
        # Optional deps collected for reporting
        self.optdeps: Dict[str, List[str]] = {}

    def add_package(self, pkg_name: str, required_by: Optional[str] = None):
        """
        Recursively add a package and its dependencies to the graph.
        """
        # Parse potential version constraint in the name
        name, op, req_ver = parse_dep(pkg_name)

        # If already in graph, just check constraints if any
        if name in self.nodes:
            if op and req_ver:
                self._check_version(self.nodes[name], op, req_ver)
            return

        # 1. Check LocalDB (already installed)
        installed = self.local_db.get(name)
        if installed:
            # If installed, we might still need to check constraints
            if op and req_ver:
                self._check_version(installed, op, req_ver)
            # We don't add already installed packages as nodes to be installed,
            # UNLESS they are explicitly requested or need upgrading (handled elsewhere).
            # For this Phase 2, we skip installed packages in the DAG.
            return

        # 2. Check SyncDB
        pkg = self.sync_db.get(name)

        # 3. Check AURDB
        if not pkg:
            pkg = self.aur_db.info(name)

        if not pkg:
            raise DependencyNotFoundError(name, required_by or "user request")

    # ── Internal ─────────────────────────────────────────────

        # Verify version constraint if it's a direct dependency
        if op and req_ver:
            self._check_version(pkg, op, req_ver)

        # Add to graph
        self.nodes[name] = pkg
        self.edges[name] = set()

        # Resolve dependencies
        deps_to_resolve = pkg.deps[:]
        if self.include_makedeps:
            deps_to_resolve += pkg.makedeps

        for dep_str in deps_to_resolve:
            dep_name, _, _ = parse_dep(dep_str)
            
            # Recurse
            self.add_package(dep_str, required_by=name)
            
            # Add edge if the dependency was actually added as a node (not skipped/installed)
            # Actually, topological sorter needs all edges. 
            # If dep is already installed, it's not a node in "to-install" graph.
            if dep_name in self.nodes:
                self.edges[name].add(dep_name)

        # Track optional deps
        if pkg.optdeps:
            self.optdeps[name] = pkg.optdeps

    def _check_version(self, pkg: Package, op: str, req_ver: str):
        v1 = Version(pkg.version)
        v2 = Version(req_ver)

        satisfied = False
        if op == ">=": satisfied = (v1 >= v2)
        elif op == "<=": satisfied = (v1 <= v2)
        elif op == ">":  satisfied = (v1 > v2)
        elif op == "<":  satisfied = (v1 < v2)
        elif op == "=":  satisfied = (v1 == v2)
        elif op == "==": satisfied = (v1 == v2)

        if not satisfied:
            raise VersionConstraintError(pkg.name, f"{op}{req_ver}", pkg.version)

    def get_graph_data(self) -> Dict[str, Set[str]]:
        """Returns the edges in a format suitable for TopologicalSorter."""
        return self.edges
