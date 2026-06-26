# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  resolver/graph.py — dependency graph builder
# ============================================================

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Set, Dict, List
from ..db.models import Package
from ..db.sync_db import SyncDB
from ..db.aur_db import AURDB
from ..db.local_db import LocalDB
from ..exceptions import DependencyNotFoundError, VersionConstraintError
from ..libsven import parse_dep, dep_satisfied, vercmp

# Soname ABI version constraints come in two forms:
#   • "=6-64" / "=0.11-64" — SONAME major-minor (libfoo.so=X-Y), pacman style
#   • "=4.0"  / "=8"       — bare pkgver with no pkgrel component (libnettle.so=4.0)
# Both live in a completely different namespace from full pacman package
# versions (e.g. "4.0-1") and will never compare equal under vercmp even
# when the installed package genuinely satisfies the dependency.
# Detection: req_ver is purely numeric/dotted with no "-" while pkg.version
# has a pkgrel ("-" present), OR req_ver matches the classic X-Y soname form.
_SONAME_VER_RE = re.compile(r'^[\d.]+(?:-64|-32)$')
_BARE_VER_RE   = re.compile(r'^[\d.]+$')   # e.g. "4.0", "8", "1.6.2"


class Version:
    """
    Arch-compatible version comparison via C sven_vercmp.
    """
    def __init__(self, v_str: str):
        self.v_str = v_str

    def __lt__(self, other: 'Version'):  return vercmp(self.v_str, other.v_str) <  0
    def __le__(self, other: 'Version'):  return vercmp(self.v_str, other.v_str) <= 0
    def __gt__(self, other: 'Version'):  return vercmp(self.v_str, other.v_str) >  0
    def __ge__(self, other: 'Version'):  return vercmp(self.v_str, other.v_str) >= 0
    def __eq__(self, other: 'Version'):  return vercmp(self.v_str, other.v_str) == 0


class DependencyGraph:
    """
    Builds a Directed Acyclic Graph of package dependencies.
    """

    def __init__(
        self,
        sync_db: SyncDB,
        aur_db: AURDB,
        local_db: LocalDB,
        include_makedeps: bool = False,
        resolve_workers: int = 4,
    ):
        self.sync_db = sync_db
        self.aur_db  = aur_db
        self.local_db = local_db
        self.include_makedeps = include_makedeps
        self.resolve_workers = max(1, resolve_workers)

        # Node map: name -> Package
        self.nodes: Dict[str, Package] = {}
        # Edge map: name -> set of dependency names
        self.edges: Dict[str, Set[str]] = {}
        # Optional deps collected for reporting
        self.optdeps: Dict[str, List[str]] = {}

        # Packages whose version check was skipped (unverified, BLFS/LFS
        # placeholder, or soname-ABI constraint mismatch). Collected here
        # instead of warning per-call so callers can print ONE consolidated
        # summary after resolution finishes, rather than spamming duplicate
        # warnings for every edge that references the same package.
        self.placeholder_packages: Set[str] = set()

    def add_package(
        self,
        pkg_name: str,
        required_by: Optional[str] = None,
        resolved_pkg: Optional[Package] = None,
    ):
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
        # If it's installed AND it is just a dependency (required_by is not None),
        # we skip adding it to the graph. If it's a top-level target (required_by is None),
        # we must add it so InstallTransaction can evaluate if it needs an upgrade.
        if installed and required_by is not None and not resolved_pkg:
            if op and req_ver:
                try:
                    self._check_version(installed, op, req_ver)
                    return
                except VersionConstraintError:
                    pass
            else:
                return

        pkg = resolved_pkg or self._resolve_package(name, op, req_ver, required_by)

        # 2. Check Graph Cache (already resolving this package by its REAL name)
        if pkg.name in self.nodes:
            if op and req_ver:
                self._check_version(self.nodes[pkg.name], op, req_ver)
            return

        # Add to graph using the REAL package name as the primary key
        name = pkg.name
        self.nodes[name] = pkg
        self.edges[name] = set()

        # Resolve dependencies
        deps_to_resolve = pkg.deps[:]
        if self.include_makedeps:
            deps_to_resolve += pkg.makedeps
            
        # Seamlessly bootstrap makepkg/fakeroot if building from AUR
        if pkg.origin == "aur":
            if "pacman" not in deps_to_resolve:
                deps_to_resolve.append("pacman")
            if "fakeroot" not in deps_to_resolve:
                deps_to_resolve.append("fakeroot")
            if "debugedit" not in deps_to_resolve:
                deps_to_resolve.append("debugedit")

        resolved_deps = self._resolve_dependencies_parallel(deps_to_resolve, required_by=name)

        for dep_str, dep_pkg in resolved_deps:
            dep_name, _, _ = parse_dep(dep_str)

            # Recurse using the already-resolved package metadata when available.
            self.add_package(dep_str, required_by=name, resolved_pkg=dep_pkg)
            
            # Use the canonical package name for the edge
            if dep_pkg and dep_pkg.name in self.nodes:
                self.edges[name].add(dep_pkg.name)

        # Track optional deps
        if pkg.optdeps:
            self.optdeps[name] = pkg.optdeps

    def _check_version(self, pkg: Package, op: str, req_ver: str):
        """Verify installed version satisfies constraint using C sven_dep_satisfied.

        Packages with unverified, BLFS/LFS-placeholder, or soname-ABI-style
        versions are recorded in self.placeholder_packages instead of being
        warned about individually — the caller prints one consolidated
        reinstall prompt after resolution finishes.
        """
        if not op or not req_ver:
            return
        if not pkg.version_verified:
            self.placeholder_packages.add(pkg.name)
            return
        # BLFS/LFS adopted packages carry placeholder versions like "BLFS-260.1-2"
        # or "LFS-BASE" that are incomparable to Arch/soname version constraints.
        # Treat them as unverified so they don't block dependency resolution.
        if pkg.version.startswith(("BLFS-", "LFS-")):
            self.placeholder_packages.add(pkg.name)
            return
        if dep_satisfied(pkg.version, op, req_ver):
            return
        # Soname ABI constraint checked against a full pkgver-pkgrel string —
        # different versioning namespaces, never directly comparable.
        # Two known soname forms:
        #   X-Y  (e.g. =6-64, =0-32)  — classic pacman SONAME major-minor
        #   X.Y  (e.g. =4.0, =8)      — bare pkgver without pkgrel component
        # The second form is detected when req_ver is purely numeric/dotted
        # (no "-") while the installed version carries a pkgrel ("-" present).
        if op == "=":
            if _SONAME_VER_RE.match(req_ver):
                self.placeholder_packages.add(pkg.name)
                return
            if _BARE_VER_RE.match(req_ver) and "-" in pkg.version:
                self.placeholder_packages.add(pkg.name)
                return
        raise VersionConstraintError(pkg.name, f"{op}{req_ver}", pkg.version)

    def warn_placeholder_packages(self) -> None:
        """
        Print ONE consolidated warning for every package that skipped a strict
        version check during resolution (unverified, BLFS/LFS, or soname-ABI
        mismatch) — instead of warning once per dependency edge that touches
        the same package.
        """
        if not self.placeholder_packages:
            return
        from ..ui.output import print_warning
        names = ", ".join(sorted(self.placeholder_packages))
        count = len(self.placeholder_packages)
        plural = "package" if count == 1 else "packages"
        print_warning(
            f"{count} {plural} skipped strict version checks (unverified / "
            f"BLFS-LFS / soname-ABI mismatch): {names}. "
            f"Reinstall {'it' if count == 1 else 'them'} via Sven for precise package tracking."
        )

    def _resolve_package(
        self,
        name: str,
        op: Optional[str],
        req_ver: Optional[str],
        required_by: Optional[str],
    ) -> Package:
        """Resolve a single package from sync DB, cache, or AUR."""
        pkg = self.sync_db.get(name)

        # If we have an exact version requirement and SyncDB version doesn't match,
        # OR if not in SyncDB, check CACHE.
        if op == "=" and req_ver:
            if not pkg or pkg.version != req_ver:
                cache_pkg = self._find_in_cache(name, req_ver)
                if cache_pkg:
                    pkg = cache_pkg

        if not pkg and self.aur_db:
            pkg = self.aur_db.info(name)

        if not pkg:
            raise DependencyNotFoundError(name, required_by or "user request")

        if op and req_ver:
            self._check_version(pkg, op, req_ver)

        return pkg

    def _resolve_dependency(self, dep_str: str, required_by: str) -> tuple[str, Optional[Package]]:
        """
        Resolve dependency metadata in parallel before recursing into the graph.
        Installed dependencies are returned as None so the recursion can skip them.
        """
        dep_name, op, req_ver = parse_dep(dep_str)

        if dep_name in self.nodes:
            if op and req_ver:
                self._check_version(self.nodes[dep_name], op, req_ver)
            return dep_str, self.nodes[dep_name]

        installed = self.local_db.get(dep_name)
        if installed:
            if op and req_ver:
                try:
                    self._check_version(installed, op, req_ver)
                    return dep_str, None
                except VersionConstraintError:
                    pass
            else:
                return dep_str, None

        return dep_str, self._resolve_package(dep_name, op, req_ver, required_by)

    def _resolve_dependencies_parallel(
        self,
        deps_to_resolve: list[str],
        *,
        required_by: str,
    ) -> list[tuple[str, Optional[Package]]]:
        """
        Resolve dependency metadata concurrently while keeping graph mutation
        deterministic and single-threaded.
        """
        if len(deps_to_resolve) <= 1:
            return [self._resolve_dependency(dep_str, required_by) for dep_str in deps_to_resolve]

        max_workers = min(self.resolve_workers, len(deps_to_resolve))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._resolve_dependency, dep_str, required_by)
                for dep_str in deps_to_resolve
            ]
            return [future.result() for future in futures]

    def _find_in_cache(self, name: str, req_ver: str) -> Optional[Package]:
        """
        Scan /var/cache/sven/pkgs for a specific version.
        """
        from ..constants import CACHE_PKGS
        from pathlib import Path
        cache_path = Path(CACHE_PKGS)
        if not cache_path.exists():
            return None

        for f in cache_path.iterdir():
            if f.name.startswith(f"{name}-{req_ver}-") and any(f.name.endswith(ext) for ext in [".pkg.tar.zst", ".pkg.tar.xz"]):
                # Mock a package object from the filename
                return Package(
                    name=name,
                    version=req_ver,
                    filename=f.name,
                    repo="cache",
                    origin="official",
                )
        return None

    def get_graph_data(self) -> Dict[str, Set[str]]:
        """Returns the edges in a format suitable for TopologicalSorter."""
        return self.edges
