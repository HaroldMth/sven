# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  security/hook_scanner.py — scan PKGBUILDs for dangerous patterns
# ============================================================
#
#  Before running makepkg, scan the PKGBUILD and any .install
#  hook files for dangerous shell patterns. If found, warn the
#  user loudly and require explicit approval.
# ============================================================

import re
from pathlib import Path
from typing import NamedTuple

from ..constants import DANGEROUS_HOOK_PATTERNS


class ScanResult(NamedTuple):
    """Result of a security scan on a PKGBUILD or hook file."""
    safe: bool
    findings: list[dict]   # [{file, line_no, pattern, line_content}]


def scan_file(filepath: str, patterns: list[str] = None) -> list[dict]:
    """
    Scan a single file for dangerous patterns.
    Returns a list of findings.
    """
    if patterns is None:
        patterns = list(DANGEROUS_HOOK_PATTERNS)

    findings = []
    path = Path(filepath)

    if not path.exists() or not path.is_file():
        return findings

    try:
        content = path.read_text(errors="replace")
    except OSError:
        return findings

    for line_no, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#"):
            continue

        for pattern in patterns:
            if pattern in stripped:
                findings.append({
                    "file": str(path.name),
                    "line_no": line_no,
                    "pattern": pattern,
                    "line_content": stripped[:120],
                })

    return findings


def scan_pkgbuild_dir(pkg_dir: str) -> ScanResult:
    """
    Scan an entire PKGBUILD directory for dangerous patterns.
    Checks: PKGBUILD, *.install, *.sh files.
    """
    dirpath = Path(pkg_dir)
    all_findings = []

    # Files to scan
    targets = []

    pkgbuild = dirpath / "PKGBUILD"
    if pkgbuild.exists():
        targets.append(pkgbuild)

    # .install hooks
    for f in dirpath.glob("*.install"):
        targets.append(f)

    # Any shell scripts
    for f in dirpath.glob("*.sh"):
        targets.append(f)

    for target in targets:
        findings = scan_file(str(target))
        all_findings.extend(findings)

    return ScanResult(
        safe=len(all_findings) == 0,
        findings=all_findings,
    )


def print_scan_warnings(result: ScanResult, pkg_name: str):
    """Print security warnings to the user."""
    if result.safe:
        return

    print(f"\n   ╭{'─' * 56}╮")
    print(f"   │  ⚠  SECURITY WARNING — {pkg_name:<30s} │")
    print(f"   ╰{'─' * 56}╯\n")
    print(f"   Found {len(result.findings)} potentially dangerous pattern(s):\n")

    for f in result.findings:
        print(f"   [{f['file']}:{f['line_no']}] Pattern: {f['pattern']}")
        print(f"     → {f['line_content']}")
        print()

    print("   These patterns may indicate malicious or unsafe behavior.")
    print("   Review the PKGBUILD carefully before proceeding.\n")


def prompt_user_approval(pkg_name: str) -> bool:
    """
    Ask the user if they want to proceed after security warnings.
    Returns True if approved, False if rejected.
    """
    try:
        response = input(
            f"   Continue building {pkg_name}? [y/N] "
        ).strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False
