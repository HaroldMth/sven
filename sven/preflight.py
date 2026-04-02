# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  preflight.py — startup dependency and environment checks
# ============================================================
#
#  Runs before any sven command to verify the environment.
#  Reports missing tools with clear instructions to fix.
# ============================================================

import shutil
import sys
from typing import NamedTuple


class CheckResult(NamedTuple):
    name: str
    available: bool
    detail: str
    fix_hint: str


def check_python_version() -> CheckResult:
    """Verify Python 3.9+ is available."""
    ver = sys.version_info
    ok = ver >= (3, 9)
    return CheckResult(
        name="Python 3.9+",
        available=ok,
        detail=f"{ver.major}.{ver.minor}.{ver.micro}",
        fix_hint="Rebuild Python >= 3.9 from source (LFS Chapter 8)",
    )


def check_requests() -> CheckResult:
    """Check if the requests library is importable."""
    try:
        import requests
        return CheckResult(
            name="requests",
            available=True,
            detail=requests.__version__,
            fix_hint="",
        )
    except ImportError:
        return CheckResult(
            name="requests",
            available=False,
            detail="not installed",
            fix_hint="pip install requests  (or: python3 -m ensurepip && pip install requests)",
        )


def check_gnupg() -> CheckResult:
    """Check if GPG verification is possible (library or binary)."""
    # Check python-gnupg
    try:
        import gnupg
        return CheckResult(
            name="GPG (python-gnupg)",
            available=True,
            detail="python-gnupg library",
            fix_hint="",
        )
    except ImportError:
        pass

    # Check gpg/gpg2 binary
    for binary in ("gpg2", "gpg"):
        if shutil.which(binary):
            return CheckResult(
                name=f"GPG ({binary})",
                available=True,
                detail=f"{binary} binary found",
                fix_hint="",
            )

    return CheckResult(
        name="GPG",
        available=False,
        detail="neither python-gnupg nor gpg/gpg2 found",
        fix_hint="Install gnupg2 from LFS BLFS book, or: pip install python-gnupg",
    )


def check_git() -> CheckResult:
    """Check if git is available (needed for AUR)."""
    if shutil.which("git"):
        return CheckResult(
            name="git",
            available=True,
            detail="found in PATH",
            fix_hint="",
        )
    return CheckResult(
        name="git",
        available=False,
        detail="not found",
        fix_hint="Install git from source (BLFS) — required for AUR packages",
    )


def check_readelf() -> CheckResult:
    """Check if readelf is available (needed for ABI compat checks)."""
    if shutil.which("readelf"):
        return CheckResult(
            name="readelf",
            available=True,
            detail="found in PATH",
            fix_hint="",
        )
    return CheckResult(
        name="readelf",
        available=False,
        detail="not found",
        fix_hint="Install binutils (should be in LFS base — check /usr/bin/readelf)",
    )


def check_tar() -> CheckResult:
    """Check if tar supports zstd (needed for .pkg.tar.zst)."""
    if not shutil.which("tar"):
        return CheckResult(
            name="tar (zstd)",
            available=False,
            detail="tar not found",
            fix_hint="Install tar from LFS Chapter 8",
        )

    # Check zstd support
    if shutil.which("zstd") or shutil.which("unzstd"):
        return CheckResult(
            name="tar (zstd)",
            available=True,
            detail="tar + zstd found",
            fix_hint="",
        )

    return CheckResult(
        name="tar (zstd)",
        available=False,
        detail="zstd not found — cannot extract .pkg.tar.zst",
        fix_hint="Install zstd from BLFS: https://facebook.github.io/zstd/",
    )


# ── Run all checks ──────────────────────────────────────────

def run_preflight() -> tuple[bool, list[CheckResult]]:
    """
    Run all preflight checks.
    Returns (all_critical_ok, results_list).
    """
    checks = [
        check_python_version(),
        check_requests(),
        check_gnupg(),
        check_git(),
        check_readelf(),
        check_tar(),
    ]

    # requests and GPG are critical; git/readelf are important but not fatal
    critical = {"Python 3.9+", "requests"}
    all_ok = all(
        c.available for c in checks if c.name in critical
    )

    return all_ok, checks


def print_preflight_report(results: list[CheckResult]):
    """Pretty-print preflight check results."""
    print("\n   ╭──────────────────────────────────────────╮")
    print("   │         Sven Preflight Check             │")
    print("   ╰──────────────────────────────────────────╯\n")

    for r in results:
        icon = "✓" if r.available else "✗"
        color_status = "OK" if r.available else "MISSING"
        print(f"   {icon}  {r.name:<20s}  {color_status:<8s}  {r.detail}")
        if not r.available and r.fix_hint:
            print(f"      └─ Fix: {r.fix_hint}")

    print()
