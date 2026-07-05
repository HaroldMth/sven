# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  installer/alpm_mirror.py — Write ALPM-compatible local DB entries
# ============================================================
#
#  Sven is the primary package manager. This module writes a
#  *read-only compatibility mirror* into /var/lib/pacman/local/
#  so that pacman -Q, -Qi, -Qo, -Ql can QUERY Sven-installed packages.
#
#  SAFETY DESIGN:
#  • We write ONLY "desc" (metadata). No "files" list.
#  • We write a ".sven" sidecar file (JSON) for our own tracking.
#  • Without "files", pacman -R fails safely with "missing files database".
#  • Without "mtree", pacman -Qk fails gracefully.
#  • Pacman can SEE the package but cannot safely REMOVE it.
#  • Removal is always delegated back to Sven.
# ============================================================

import json
import os
import time
from pathlib import Path
from typing import Optional

from ..config import get_config
from ..exceptions import SvenError


def _write_desc(pkg_dir: Path, pkg, reason: int = 0) -> None:
    """Write ALPM desc file from a Package object."""
    lines = []

    def field(name: str, value: str):
        lines.append(f"%{name}%")
        lines.append(value)

    def list_field(name: str, values: list):
        if values:
            lines.append(f"%{name}%")
            lines.extend(values)

    field("NAME",        pkg.name)
    field("VERSION",     pkg.version)
    field("DESC",        pkg.desc or "")
    field("URL",         pkg.url or "")
    field("ARCH",        pkg.arch or "x86_64")
    field("BUILDDATE",   str(int(pkg.builddate or 0)))
    field("INSTALLDATE", str(int(time.time())))
    field("PACKAGER",    pkg.packager or "Sven Package Manager")
    field("SIZE",        str(int(pkg.isize or 0)))
    field("REASON",      str(int(reason)))  # 0 = explicit, 1 = dependency

    list_field("LICENSE",     pkg.license or [])
    list_field("DEPENDS",     pkg.deps or [])
    list_field("OPTDEPENDS",  pkg.optdeps or [])
    list_field("CONFLICTS",   pkg.conflicts or [])
    list_field("PROVIDES",    pkg.provides or [])
    list_field("REPLACES",    pkg.replaces or [])

    # We intentionally do NOT write %SVEN% or any custom field in desc.
    # All Sven metadata lives in the sidecar .sven file.

    desc_path = pkg_dir / "desc"
    desc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_sven_sidecar(pkg_dir: Path, pkg, reason: int = 0) -> None:
    """Write a .sven sidecar file with Sven-specific metadata."""
    sidecar = {
        "name": pkg.name,
        "version": pkg.version,
        "origin": pkg.origin or "official",
        "reason": reason,
        "managed_by": "sven",
        "timestamp": int(time.time()),
    }
    sidecar_path = pkg_dir / ".sven"
    sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")


def write_alpm_local_entry(pkg, reason: int = 0) -> None:
    """
    Write a pacman-compatible (read-only) local DB entry for a Sven-installed package.

    Writes:
      • desc  — ALPM metadata (pacman -Q, -Qi, -Qo can read this)
      • .sven — Sven sidecar marker (JSON, ignored by pacman)

    Does NOT write:
      • files — prevents pacman -R from operating safely
      • mtree — prevents pacman -Qk from running (acceptable)
      • install — Sven handles its own hooks
    """
    config = get_config()
    root = Path(config.install_root or "/")
    local_dir = root / "var/lib/pacman/local"
    local_dir.mkdir(parents=True, exist_ok=True)

    pkg_dir = local_dir / f"{pkg.name}-{pkg.version}"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    _write_desc(pkg_dir, pkg, reason=reason)
    _write_sven_sidecar(pkg_dir, pkg, reason=reason)

    # We do NOT write "files" or "mtree".
    # This is intentional: it makes pacman -R fail safely.


def remove_alpm_local_entry(pkg_name: str, pkg_version: str) -> None:
    """Remove a pacman-compatible local DB entry when Sven removes a package."""
    config = get_config()
    root = Path(config.install_root or "/")
    local_dir = root / "var/lib/pacman/local"
    pkg_dir = local_dir / f"{pkg_name}-{pkg_version}"

    if pkg_dir.exists():
        import shutil
        shutil.rmtree(pkg_dir)


def is_sven_managed_alpm_entry(pkg_name: str, pkg_version: str) -> bool:
    """Check whether a pacman local DB entry was written by Sven (has .sven sidecar)."""
    config = get_config()
    root = Path(config.install_root or "/")
    sidecar_path = root / "var/lib/pacman/local" / f"{pkg_name}-{pkg_version}" / ".sven"
    return sidecar_path.exists()


def read_sven_sidecar(pkg_name: str, pkg_version: str) -> Optional[dict]:
    """Read the .sven sidecar for a package, if it exists."""
    config = get_config()
    root = Path(config.install_root or "/")
    sidecar_path = root / "var/lib/pacman/local" / f"{pkg_name}-{pkg_version}" / ".sven"
    if not sidecar_path.exists():
        return None
    try:
        return json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
