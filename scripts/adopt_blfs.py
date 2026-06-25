# ============================================================
#  Sven — Seven OS Adoption Script (BLFS Auto-Discovery)
#  HANS TECH © 2024 — GPL v3
#  scripts/adopt_blfs.py — scans the system and registers
#  all detected packages into Sven's LocalDB
# ============================================================
"""
This script scans standard system directories for installed
libraries, binaries, and shared objects. It then matches them
against entries in the SyncDB to determine which Arch packages
are already present on the system (built manually from LFS/BLFS).

Usage (inside chroot):
    python3 scripts/adopt_blfs.py

Or with PYTHONPATH:
    PYTHONPATH=. python3 scripts/adopt_blfs.py
"""

import argparse
import os
import sys
from pathlib import Path

# Add project to path
sys.path.append(os.getcwd())

from sven.config import get_config
from sven.db.local_db import LocalDB
from sven.db.sync_db import SyncDB
from sven.db.models import Package
from sven.version_probe import generic_probe


# ── Directories to scan ─────────────────────────────────────

LIB_SCAN_DIRS = ["/usr/lib", "/usr/lib64", "/lib", "/lib64",
                  "/usr/lib/x86_64-linux-gnu", "/lib/x86_64-linux-gnu"]
BIN_SCAN_DIRS = ["/usr/bin", "/usr/sbin"]
PC_SCAN_DIRS  = ["/usr/lib/pkgconfig", "/usr/lib64/pkgconfig",
                  "/usr/share/pkgconfig", "/usr/lib/x86_64-linux-gnu/pkgconfig"]


def scan_shared_libraries() -> dict[str, str]:
    """Find all .so files on the system. Returns {basename: full_path}."""
    libs = {}
    for scan_dir in LIB_SCAN_DIRS:
        p = Path(scan_dir)
        if not p.exists():
            continue
        for f in p.rglob("*.so*"):
            if f.is_file() or f.is_symlink():
                libs[f.name] = str(f)
    return libs


def scan_binaries() -> dict[str, str]:
    """Find all binaries in standard paths. Returns {name: full_path}."""
    bins = {}
    for scan_dir in BIN_SCAN_DIRS:
        p = Path(scan_dir)
        if not p.exists():
            continue
        for f in p.iterdir():
            if f.is_file() or f.is_symlink():
                bins[f.name] = str(f)
    return bins


def scan_pkgconfig() -> dict[str, str]:
    """Find all .pc files. Returns {stem: full_path}."""
    pcs = {}
    for scan_dir in PC_SCAN_DIRS:
        p = Path(scan_dir)
        if not p.exists():
            continue
        for f in p.glob("*.pc"):
            pcs[f.stem] = str(f)
    return pcs


def scan_include_dirs() -> dict[str, str]:
    """Find all include directories (headers). Returns {lowername: full_path}."""
    dirs = {}
    p = Path("/usr/include")
    if p.exists():
        for d in p.iterdir():
            if d.is_dir():
                dirs[d.name.lower()] = str(d)
    return dirs


def match_packages(sync_db: SyncDB, local_db: LocalDB,
                   system_libs: dict, system_bins: dict,
                   system_pcs: dict, system_includes: dict,
                   min_score: int = 5) -> list[tuple]:
    """
    Match system artifacts against SyncDB entries.
    Returns a list of (pkg, score, reasons, evidence_files) tuples.

    A candidate is only accepted if EITHER:
      - it has an exact binary-name match (strong signal on its own), OR
      - signals from at least 2 distinct categories combine to >= min_score

    This prevents a single generic/coincidental match (e.g. a common .so
    naming pattern) from being enough on its own to adopt the wrong package.
    """
    already_installed = set(local_db.list_installed())
    candidates = []

    all_packages = sync_db.all_packages()

    for pkg in all_packages:
        if pkg.name in already_installed:
            continue

        score = 0
        reasons = []
        categories: set[str] = set()
        evidence: set[str] = set()

        # Check 1: Package name matches a binary
        if pkg.name in system_bins:
            score += 10
            reasons.append(f"binary: {pkg.name}")
            categories.add("binary")
            evidence.add(system_bins[pkg.name])

        # Check 2: Package provides match installed .so files
        for prov in pkg.provides:
            prov_name = prov.split("=")[0].split(">")[0].split("<")[0].strip()
            if prov_name in system_libs:
                score += 8
                reasons.append(f"provides: {prov_name}")
                categories.add("provides")
                evidence.add(system_libs[prov_name])

        # Check 3: Package name matches a .pc file
        pkg_lower = pkg.name.lower()
        for pc_name, pc_path in system_pcs.items():
            if pc_name.lower() == pkg_lower or pc_name.lower().startswith(pkg_lower):
                score += 6
                reasons.append(f"pkgconfig: {pc_name}")
                categories.add("pkgconfig")
                evidence.add(pc_path)
                break

        # Check 4: Package name matches an include directory
        if pkg_lower in system_includes:
            score += 4
            reasons.append(f"include: {pkg_lower}")
            categories.add("include")
            evidence.add(system_includes[pkg_lower])

        # Check 5: Common .so naming convention ("libfoo" pkg -> "libfoo.so")
        expected_so = f"{pkg.name}.so"
        for so_name, so_path in system_libs.items():
            if so_name == expected_so or so_name.startswith(expected_so + "."):
                score += 7
                reasons.append(f"lib: {so_name}")
                categories.add("lib_exact")
                evidence.add(so_path)
                break

        # Check 6: lib-prefixed convention ("foo" pkg -> "libfoo.so")
        if not pkg.name.startswith("lib"):
            alt_prefix = f"lib{pkg.name}.so"
            for so_name, so_path in system_libs.items():
                if so_name == alt_prefix or so_name.startswith(alt_prefix + "."):
                    score += 5
                    reasons.append(f"lib: {so_name}")
                    categories.add("lib_prefixed")
                    evidence.add(so_path)
                    break

        strong_alone = "binary" in categories
        enough_categories = len(categories) >= 2

        if score >= min_score and (strong_alone or enough_categories):
            candidates.append((pkg, score, reasons, evidence))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


def adopt(min_score: int = 5, dry_run: bool = False, assume_yes: bool = False):
    config = get_config()
    local_db = LocalDB()
    sync_db = SyncDB()

    print("   ╭──────────────────────────────────────────────────╮")
    print("   │  Sven BLFS Auto-Discovery & Adoption             │")
    print("   ╰──────────────────────────────────────────────────╯")
    print()

    print("   [1/3] Scanning filesystem...")
    system_libs = scan_shared_libraries()
    system_bins = scan_binaries()
    system_pcs = scan_pkgconfig()
    system_includes = scan_include_dirs()

    print(f"         Found {len(system_libs)} shared libraries")
    print(f"         Found {len(system_bins)} binaries")
    print(f"         Found {len(system_pcs)} pkgconfig files")
    print(f"         Found {len(system_includes)} include directories")

    print("\n   [2/3] Matching against SyncDB...")
    candidates = match_packages(sync_db, local_db,
                                system_libs, system_bins,
                                system_pcs, system_includes,
                                min_score=min_score)

    if not candidates:
        print("   ✓ No new packages to adopt. LocalDB is comprehensive.")
        return

    print(f"         Detected {len(candidates)} packages already on system\n")

    for pkg, score, reasons, evidence in candidates[:20]:
        reason_str = ", ".join(reasons[:2])
        print(f"      + {pkg.name:<35} (score: {score:>2}, {reason_str})")

    if len(candidates) > 20:
        print(f"      ... and {len(candidates) - 20} more")

    print()

    if not assume_yes:
        reply = input(f"   Continue with adopting {len(candidates)} packages? [y/N]: ").strip().lower()
        if reply not in ("y", "yes"):
            print("   Aborted. No changes were made.")
            return

    print(f"   [3/3] Registering {len(candidates)} packages into LocalDB...")

    adopted = 0
    unverified = 0
    for pkg, score, reasons, evidence in candidates:
        try:
            # Cross-check against a live --version probe when the package
            # itself is a binary we found (pkg.name in system_bins). If that
            # succeeds we have a REAL, freshly-detected version. Otherwise we
            # fall back to the SyncDB version, but mark it unverified since
            # we matched this package heuristically — we can't be certain
            # the on-disk build is exactly that version.
            real_version = None
            if pkg.name in system_bins:
                real_version = generic_probe(pkg.name)

            if real_version:
                version = real_version
                verified = True
                note = "Auto-discovered from BLFS build (version confirmed via --version probe)"
            else:
                version = pkg.version
                verified = False
                note = ("Auto-discovered from BLFS build (version inferred from package "
                        "match — not independently confirmed on this system)")
                unverified += 1

            local_pkg = Package(
                name=pkg.name,
                version=version,
                version_verified=verified,
                desc=note,
                url=pkg.url or "",
                provides=pkg.provides,
                origin="local",
            )
            if not dry_run:
                local_db.register(local_pkg, files=sorted(evidence), explicit=True)
            adopted += 1
        except Exception as e:
            print(f"      ⚠ Failed to adopt {pkg.name}: {e}")

    print(f"\n   ✓ Adoption complete. Registered {adopted} packages.")
    if unverified:
        print(f"   ⚠ {unverified} package(s) registered with an unverified version "
              f"(matched heuristically, not confirmed via --version). Version-constraint "
              f"checks involving them will be skipped, not silently wrong.")
    if dry_run:
        print("   ✓ Dry-run mode: LocalDB was not modified.")
    print(f"   ✓ Sven now recognizes your full BLFS system.")


def main():
    parser = argparse.ArgumentParser(description="Auto-discover BLFS packages and adopt into Sven LocalDB")
    parser.add_argument("--min-score", type=int, default=5, help="Minimum confidence score to adopt (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Preview adoption without writing LocalDB")
    parser.add_argument("-y", "--yes", action="store_true", help="Do not prompt for confirmation")
    args = parser.parse_args()
    adopt(min_score=args.min_score, dry_run=args.dry_run, assume_yes=args.yes)


if __name__ == "__main__":
    main()
