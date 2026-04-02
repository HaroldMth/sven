# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  resolver/compat.py — deep binary compatibility checks
# ============================================================
#
#  Uses `readelf` to extract GLIBC version requirements from
#  binaries and compares them against the host's actual glibc.
#  This catches ABI mismatches that simple .so existence checks miss.
# ============================================================

import os
import re
import subprocess
from enum import Enum
from pathlib import Path
from typing import Optional

from ..db.models import Package


class CompatibilityLevel(Enum):
    BINARY_SAFE       = "BINARY_SAFE"
    SOURCE_RECOMMENDED = "SOURCE_RECOMMENDED"
    SOURCE_REQUIRED    = "SOURCE_REQUIRED"


LIB_PATHS = [
    "/lib64",
    "/usr/lib",
    "/usr/local/lib",
    "/lib/x86_64-linux-gnu",
    "/usr/lib/x86_64-linux-gnu",
]


# ── Host glibc detection ────────────────────────────────────

_host_glibc_version: Optional[str] = None

def get_host_glibc_version() -> Optional[str]:
    """
    Detect the host system's glibc version.
    Tries:  ldd --version  →  parse first line for version number
    Falls back to reading the glibc binary directly.
    """
    global _host_glibc_version
    if _host_glibc_version is not None:
        return _host_glibc_version

    # Method 1: ldd --version
    try:
        result = subprocess.run(
            ["ldd", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout or result.stderr
        # Typical output: "ldd (GNU libc) 2.38"
        match = re.search(r"(\d+\.\d+)", output)
        if match:
            _host_glibc_version = match.group(1)
            return _host_glibc_version
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Method 2: Check libc.so.6 directly
    for path in ["/lib64/libc.so.6", "/lib/libc.so.6", "/usr/lib/libc.so.6"]:
        if os.path.exists(path):
            try:
                result = subprocess.run(
                    [path],
                    capture_output=True, text=True, timeout=5,
                )
                output = result.stdout or result.stderr
                match = re.search(r"release version (\d+\.\d+)", output)
                if match:
                    _host_glibc_version = match.group(1)
                    return _host_glibc_version
            except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
                continue

    return None


def _parse_version_tuple(ver: str) -> tuple:
    """Convert '2.38' to (2, 38) for comparison."""
    parts = ver.split(".")
    return tuple(int(p) for p in parts)


# ── readelf-based ABI checking ──────────────────────────────

def extract_glibc_requirements(filepath: str) -> list[str]:
    """
    Run `readelf -V` on a binary/shared library and extract
    GLIBC_X.XX version requirement tags.

    Returns a list like ['2.17', '2.34', '2.38'].
    """
    try:
        result = subprocess.run(
            ["readelf", "-V", filepath],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []

        versions = set()
        for match in re.finditer(r"GLIBC_(\d+\.\d+)", result.stdout):
            versions.add(match.group(1))

        return sorted(versions, key=_parse_version_tuple)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def check_elf_interpreter(filepath: str) -> Optional[str]:
    """
    Extract the ELF interpreter (e.g. /lib64/ld-linux-x86-64.so.2)
    from a binary using readelf.
    """
    try:
        result = subprocess.run(
            ["readelf", "-l", filepath],
            capture_output=True, text=True, timeout=10,
        )
        match = re.search(r"\[Requesting program interpreter: (.+?)\]", result.stdout)
        if match:
            return match.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


# ── Main compatibility check ────────────────────────────────

def check_binary_compatibility(pkg: Package) -> CompatibilityLevel:
    """
    Check if a binary package is safe to install on this Seven OS (LFS).

    Level 1: Check .so dependencies exist on the system
    Level 2: If a cached .pkg.tar.zst exists, scan its ELF binaries
             for GLIBC version requirements vs host glibc

    Returns: BINARY_SAFE | SOURCE_RECOMMENDED | SOURCE_REQUIRED
    """
    # ── Level 1: Shared library existence check ──
    libraries_needed = []

    for dep in pkg.deps:
        if ".so" in dep:
            lib_name = dep.split("=")[0].split(">")[0].split("<")[0].strip()
            libraries_needed.append(lib_name)

    missing_libs = []
    for lib in libraries_needed:
        found = False
        for path in LIB_PATHS:
            if (Path(path) / lib).exists():
                found = True
                break
        if not found:
            missing_libs.append(lib)

    if missing_libs:
        return CompatibilityLevel.SOURCE_REQUIRED

    # ── Level 2: GLIBC ABI version check ──
    host_glibc = get_host_glibc_version()
    if host_glibc is None:
        # Can't determine host glibc — recommend source build to be safe
        return CompatibilityLevel.SOURCE_RECOMMENDED

    host_ver = _parse_version_tuple(host_glibc)

    # Check known system binaries that would be installed by this package
    # We scan standard lib dirs for any .so that matches the pkg provides
    for prov in pkg.provides:
        prov_name = prov.split("=")[0].split(">")[0].split("<")[0].strip()
        if ".so" in prov_name:
            for path in LIB_PATHS:
                full = Path(path) / prov_name
                if full.exists():
                    required = extract_glibc_requirements(str(full))
                    if required:
                        max_required = _parse_version_tuple(required[-1])
                        if max_required > host_ver:
                            return CompatibilityLevel.SOURCE_REQUIRED

    return CompatibilityLevel.BINARY_SAFE


def check_package_abi(pkg_archive_path: str) -> dict:
    """
    Deep ABI check on a downloaded .pkg.tar.zst archive.
    Extracts ELF binaries and checks their GLIBC requirements.

    Returns: {
        'compatible': bool,
        'host_glibc': str,
        'max_required_glibc': str or None,
        'interpreter_ok': bool,
        'details': list[str]
    }
    """
    import tarfile

    host_glibc = get_host_glibc_version()
    result = {
        "compatible": True,
        "host_glibc": host_glibc,
        "max_required_glibc": None,
        "interpreter_ok": True,
        "details": [],
    }

    if host_glibc is None:
        result["compatible"] = False
        result["details"].append("Cannot determine host glibc version")
        return result

    host_ver = _parse_version_tuple(host_glibc)
    max_glibc = (0, 0)

    try:
        with tarfile.open(pkg_archive_path, "r:*") as tar:
            for member in tar.getmembers():
                # Only check regular files in bin/lib dirs
                if not member.isfile():
                    continue
                name = member.name
                if not any(
                    name.startswith(p)
                    for p in ("usr/bin/", "usr/lib/", "bin/", "lib/", "usr/sbin/", "sbin/")
                ):
                    continue

                # Extract to a temp location for readelf
                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    tar.extract(member, tmpdir)
                    extracted = os.path.join(tmpdir, member.name)

                    # Check ELF interpreter
                    interp = check_elf_interpreter(extracted)
                    if interp and not os.path.exists(interp):
                        result["interpreter_ok"] = False
                        result["details"].append(
                            f"Missing interpreter: {interp} (file: {name})"
                        )

                    # Check GLIBC versions
                    glibc_vers = extract_glibc_requirements(extracted)
                    if glibc_vers:
                        max_ver = _parse_version_tuple(glibc_vers[-1])
                        if max_ver > max_glibc:
                            max_glibc = max_ver

                        if max_ver > host_ver:
                            result["compatible"] = False
                            result["details"].append(
                                f"{name}: needs GLIBC_{glibc_vers[-1]}, "
                                f"host has {host_glibc}"
                            )

    except (tarfile.TarError, OSError) as e:
        result["details"].append(f"Archive read error: {e}")

    if max_glibc > (0, 0):
        result["max_required_glibc"] = ".".join(str(v) for v in max_glibc)

    return result
