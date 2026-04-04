# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  builder/makepkg.py — build packages from PKGBUILDs
# ============================================================
#
#  CRITICAL: makepkg must NEVER run as root.
#  If uid == 0, we drop to a build user via `sudo -u nobody`.
#  On success, returns the path to the built .pkg.tar.zst.
# ============================================================

import os
import glob
import subprocess
import sys
from pathlib import Path
from typing import Optional

from ..config import get_config
from ..exceptions import BuildError, RootBuildError
from ..ssl_bundle import augment_env_with_ssl_certs
from ..security.hook_scanner import (
    scan_pkgbuild_dir,
    prompt_hook_approval,
)


# ── Build user for root drop ────────────────────────────────

BUILD_USER = "nobody"


def _is_root() -> bool:
    return os.getuid() == 0


def _find_build_user() -> str:
    """
    Find a suitable non-root user for building.
    Tries 'nobody' first, then falls back to 'sven-build'.
    """
    import pwd
    for user in (BUILD_USER, "sven-build"):
        try:
            pwd.getpwnam(user)
            return user
        except KeyError:
            continue
    return BUILD_USER  # fallback — will error at runtime if missing


# ── Main build function ─────────────────────────────────────

def run_makepkg(
    pkg_dir: str,
    pkg_name: str,
    skip_security_scan: bool = False,
    interactive: bool = True,
) -> str:
    """
    Run makepkg to build a package from a PKGBUILD directory.

    Args:
        pkg_dir: Path to directory containing PKGBUILD
        pkg_name: Package name (for error messages)
        skip_security_scan: If True, bypass hook scanner (NOT RECOMMENDED)
        interactive: If True, show build output in real-time

    Returns:
        Absolute path to the built .pkg.tar.zst file

    Raises:
        RootBuildError: If running as root and cannot drop privileges
        BuildError: If makepkg fails
    """
    config = get_config()
    pkg_path = Path(pkg_dir)

    # ── Validate directory ──
    pkgbuild = pkg_path / "PKGBUILD"
    if not pkgbuild.exists():
        raise BuildError(pkg_name, f"No PKGBUILD found in {pkg_dir}")

    # ── Security scan ──
    if not skip_security_scan:
        scan_result = scan_pkgbuild_dir(pkg_dir)
        if not scan_result.safe:
            if interactive:
                action = prompt_hook_approval(pkg_name, scan_result)
                if action == "A":
                    raise BuildError(
                        pkg_name,
                        "Build cancelled by user after security warning",
                    )
                elif action == "S":
                    # Strip hook files to skip them
                    for h_file in list(pkg_path.glob("*.install")) + list(pkg_path.glob("*.sh")):
                        h_file.unlink()
            else:
                raise BuildError(
                    pkg_name,
                    f"Security scan found {len(scan_result.findings)} "
                    f"dangerous pattern(s). Use interactive mode to review.",
                )

    # ── Build command ──
    makeflags = f"-j{config.parallel_jobs}"

    cmd = [
        "makepkg",
        "--nodeps",        # Trust Sven for dependencies (skip pacman checks)
        "--noconfirm",     # Don't ask for confirmation
        "--clean",         # Clean after build
        "--force",         # Overwrite existing package
    ]

    env = os.environ.copy()
    env["MAKEFLAGS"] = makeflags
    env["PKGDEST"] = str(pkg_path)  # Output package to same dir
    augment_env_with_ssl_certs(env)

    # ── Root check + privilege drop ──
    if _is_root():
        build_user = _find_build_user()

        # Ensure build dir is owned by build user
        try:
            import pwd
            pw = pwd.getpwnam(build_user)
            _chown_recursive(pkg_path, pw.pw_uid, pw.pw_gid)
        except (KeyError, OSError) as e:
            raise RootBuildError()

        # Wrap command with sudo -u
        cmd = [
            "sudo",
            "-u",
            build_user,
            "--preserve-env=MAKEFLAGS,PKGDEST,SSL_CERT_FILE,SSL_CERT_DIR,GIT_SSL_CAINFO,GIT_SSL_CAPATH,REQUESTS_CA_BUNDLE",
        ] + cmd

    # ── Run the build ──
    print(f"\n   ╭{'─' * 50}╮")
    print(f"   │  Building: {pkg_name:<38} │")
    print(f"   │  Jobs: {config.parallel_jobs:<41d} │")
    print(f"   ╰{'─' * 50}╯\n")


    try:
        if interactive:
            # Stream output to terminal in real-time
            result = subprocess.run(
                cmd,
                cwd=str(pkg_path),
                env=env,
                timeout=3600,       # 1 hour max
            )
        else:
            # Capture output silently
            result = subprocess.run(
                cmd,
                cwd=str(pkg_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=3600,
            )

    except subprocess.TimeoutExpired:
        raise BuildError(pkg_name, "Build timed out after 1 hour")
    except FileNotFoundError:
        raise BuildError(
            pkg_name,
            "makepkg not found. Install pacman/makepkg from Arch tools.",
        )

    if result.returncode != 0:
        reason = "makepkg exited with non-zero status"
        if hasattr(result, "stderr") and result.stderr:
            # Get the last few lines of stderr for context
            lines = result.stderr.strip().splitlines()
            tail = "\n".join(lines[-5:])
            reason = f"makepkg failed:\n{tail}"
        raise BuildError(pkg_name, reason)

    # ── Find built package ──
    built_pkg = _find_built_package(str(pkg_path), pkg_name)
    if not built_pkg:
        raise BuildError(
            pkg_name,
            f"Build succeeded but no .pkg.tar.zst was found in {pkg_dir}",
        )

    print(f"   ✓ Built: {Path(built_pkg).name}")
    return built_pkg


def _find_built_package(pkg_dir: str, pkg_name: str) -> Optional[str]:
    """
    Find the built .pkg.tar.zst in the package directory.
    Prefers the real package over debug/split packages.
    """
    patterns = [
        f"{pkg_name}-*.pkg.tar.zst",
        f"{pkg_name}-*.pkg.tar.xz",
        "*.pkg.tar.zst",
        "*.pkg.tar.xz",
    ]

    for pattern in patterns:
        matches = glob.glob(os.path.join(pkg_dir, pattern))
        # Always skip -debug packages — they only contain debug symbols
        matches = [m for m in matches if "-debug-" not in Path(m).name]
        if matches:
            # Sort by modification time, newest first
            matches.sort(key=os.path.getmtime, reverse=True)
            return matches[0]

    return None


def _chown_recursive(path: Path, uid: int, gid: int):
    """Recursively change ownership of a directory."""
    os.chown(str(path), uid, gid)
    for child in path.rglob("*"):
        try:
            os.chown(str(child), uid, gid)
        except OSError:
            pass


# ── Batch build (respects dep order) ────────────────────────

def build_aur_packages(
    build_order: list[dict],
    interactive: bool = True,
) -> dict[str, str]:
    """
    Build a list of AUR packages in dependency order.

    Args:
        build_order: List of dicts [{'name': str, 'dir': str}, ...]
                     ordered so deps come before dependents
        interactive: If True, show build output

    Returns:
        Dict of {pkg_name: built_archive_path}

    Raises:
        BuildError on first failure (stops remaining builds)
    """
    results = {}

    for i, pkg_info in enumerate(build_order, 1):
        name = pkg_info["name"]
        pkg_dir = pkg_info["dir"]

        print(f"\n   [{i}/{len(build_order)}] Building {name}...")

        built_path = run_makepkg(
            pkg_dir=pkg_dir,
            pkg_name=name,
            interactive=interactive,
        )
        results[name] = built_path

    return results
