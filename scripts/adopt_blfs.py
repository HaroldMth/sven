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
    python3 /home/harold/Desktop/sven/scripts/adopt_blfs.py

Or with PYTHONPATH:
    PYTHONPATH=/home/harold/Desktop/sven python3 scripts/adopt_blfs.py
"""

import sys
import os
import re
from pathlib import Path

# Add project to path
sys.path.append(os.getcwd())

from sven.config import get_config
from sven.db.local_db import LocalDB
from sven.db.sync_db import SyncDB
from sven.db.models import Package


# ── Directories to scan ─────────────────────────────────────

SCAN_DIRS = [
    "/usr/lib",
    "/usr/lib64",
    "/usr/bin",
    "/usr/sbin",
    "/usr/share/pkgconfig",
    "/usr/lib/pkgconfig",
    "/usr/include",
]

# Files that strongly indicate a package is present
# Maps: filename pattern -> likely package name(s)
# We'll also use the SyncDB provides/files data


def scan_shared_libraries() -> set[str]:
    """Find all .so files on the system."""
    libs = set()
    for scan_dir in ["/usr/lib", "/usr/lib64"]:
        p = Path(scan_dir)
        if not p.exists():
            continue
        for f in p.rglob("*.so*"):
            if f.is_file() or f.is_symlink():
                libs.add(f.name)
    return libs


def scan_binaries() -> set[str]:
    """Find all binaries in standard paths."""
    bins = set()
    for scan_dir in ["/usr/bin", "/usr/sbin"]:
        p = Path(scan_dir)
        if not p.exists():
            continue
        for f in p.iterdir():
            if f.is_file() or f.is_symlink():
                bins.add(f.name)
    return bins


def scan_pkgconfig() -> set[str]:
    """Find all .pc files (pkgconfig) on the system."""
    pcs = set()
    for scan_dir in ["/usr/lib/pkgconfig", "/usr/lib64/pkgconfig", "/usr/share/pkgconfig"]:
        p = Path(scan_dir)
        if not p.exists():
            continue
        for f in p.glob("*.pc"):
            # e.g. "Qt6Core.pc" -> "Qt6Core"
            pcs.add(f.stem)
    return pcs


def scan_include_dirs() -> set[str]:
    """Find all include directories (headers)."""
    dirs = set()
    p = Path("/usr/include")
    if p.exists():
        for d in p.iterdir():
            if d.is_dir():
                dirs.add(d.name.lower())
    return dirs


def match_packages(sync_db: SyncDB, local_db: LocalDB,
                   system_libs: set, system_bins: set,
                   system_pcs: set, system_includes: set) -> list[Package]:
    """
    Match system artifacts against SyncDB entries.
    Returns a list of Package objects that should be adopted.
    """
    already_installed = set(local_db.list_installed())
    candidates = []

    # Get ALL packages from the sync databases
    all_packages = sync_db.all_packages()

    for pkg in all_packages:
        # Skip if already in LocalDB
        if pkg.name in already_installed:
            continue

        score = 0
        reasons = []

        # Check 1: Package name matches a binary
        if pkg.name in system_bins:
            score += 10
            reasons.append(f"binary: {pkg.name}")

        # Check 2: Package provides match installed .so files
        for prov in pkg.provides:
            prov_name = prov.split("=")[0].split(">")[0].split("<")[0].strip()
            if prov_name in system_libs:
                score += 8
                reasons.append(f"provides: {prov_name}")

        # Check 3: Package name matches a .pc file
        pkg_lower = pkg.name.lower()
        for pc in system_pcs:
            if pc.lower() == pkg_lower or pc.lower().startswith(pkg_lower):
                score += 6
                reasons.append(f"pkgconfig: {pc}")
                break

        # Check 4: Package name matches an include directory
        if pkg_lower in system_includes:
            score += 4
            reasons.append(f"include: {pkg_lower}")

        # Check 5: Common .so naming convention
        # e.g. "libfoo" package -> "libfoo.so" on disk
        expected_so = f"{pkg.name}.so"
        if expected_so in system_libs:
            score += 7
            reasons.append(f"lib: {expected_so}")

        # Check 6: lib-prefixed convention
        # e.g. "foo" package -> "libfoo.so"
        if not pkg.name.startswith("lib"):
            alt_so = f"lib{pkg.name}.so"
            if alt_so in system_libs:
                score += 5
                reasons.append(f"lib: {alt_so}")

        # Threshold: need at least one strong match
        if score >= 5:
            candidates.append((pkg, score, reasons))

    # Sort by score descending
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


def adopt():
    config = get_config()
    local_db = LocalDB()
    sync_db = SyncDB()

    print("   ╭──────────────────────────────────────────────────╮")
    print("   │  Sven BLFS Auto-Discovery & Adoption             │")
    print("   ╰──────────────────────────────────────────────────╯")
    print()

    # Phase 1: Scan
    print("   [1/3] Scanning filesystem...")
    system_libs = scan_shared_libraries()
    system_bins = scan_binaries()
    system_pcs = scan_pkgconfig()
    system_includes = scan_include_dirs()

    print(f"         Found {len(system_libs)} shared libraries")
    print(f"         Found {len(system_bins)} binaries")
    print(f"         Found {len(system_pcs)} pkgconfig files")
    print(f"         Found {len(system_includes)} include directories")

    # Phase 2: Match
    print("\n   [2/3] Matching against SyncDB...")
    candidates = match_packages(sync_db, local_db,
                                system_libs, system_bins,
                                system_pcs, system_includes)

    if not candidates:
        print("   ✓ No new packages to adopt. LocalDB is comprehensive.")
        return

    print(f"         Detected {len(candidates)} packages already on system\n")

    # Show what we found
    for pkg, score, reasons in candidates[:20]:
        reason_str = ", ".join(reasons[:2])
        print(f"      + {pkg.name:<35} (score: {score:>2}, {reason_str})")

    if len(candidates) > 20:
        print(f"      ... and {len(candidates) - 20} more")

    print()

    # Phase 3: Register
    print(f"   [3/3] Registering {len(candidates)} packages into LocalDB...")

    adopted = 0
    for pkg, score, reasons in candidates:
        try:
            # Use the version from SyncDB as a reference
            # Mark as "BLFS-LOCAL" to distinguish from Sven-managed installs
            local_pkg = Package(
                name=pkg.name,
                version=f"BLFS-{pkg.version}" if not pkg.version.startswith("BLFS") else pkg.version,
                desc=pkg.desc or f"Auto-discovered from BLFS build",
                url=pkg.url or "",
                provides=pkg.provides,
                origin="explicit",
            )
            local_db.register(local_pkg, files=[], explicit=True)
            adopted += 1
        except Exception as e:
            print(f"      ⚠ Failed to adopt {pkg.name}: {e}")

    print(f"\n   ✓ Adoption complete. Registered {adopted} packages.")
    print(f"   ✓ Sven now recognizes your full BLFS system.")


if __name__ == "__main__":
    adopt()
