# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  db/pacman_sync.py — Read pacman local DB into Sven
# ============================================================
#
#  Bidirectional awareness: pacman installed something? Sven learns about it.
#  Creates lightweight Sven LocalDB entries for pacman-managed packages
#  so that `sven list` and `sven info` show the full system picture.
#
#  IMPORTANT: synced entries are marked with synced_only=True.
#  `sven remove` will refuse to remove synced-only packages,
#  directing the user to use `pacman -R` instead.
# ============================================================

import os
import time
from pathlib import Path
from typing import Optional

from .models import Package
from .local_db import LocalDB


def _parse_alpm_desc(desc_text: str) -> dict:
    """Parse an ALPM desc file (same format Sven already knows from sync_db)."""
    fields: dict[str, list[str]] = {}
    current_key = None

    for line in desc_text.splitlines():
        line = line.strip()
        if not line:
            current_key = None
            continue
        if line.startswith("%") and line.endswith("%"):
            current_key = line[1:-1]
            fields[current_key] = []
        elif current_key is not None:
            fields[current_key].append(line)

    def get(key: str) -> str:
        return fields.get(key, [""])[0]

    def get_list(key: str) -> list[str]:
        return fields.get(key, [])

    return {
        "name":        get("NAME"),
        "version":     get("VERSION"),
        "desc":        get("DESC"),
        "url":         get("URL"),
        "arch":        get("ARCH") or "x86_64",
        "builddate":   int(get("BUILDDATE") or 0),
        "packager":    get("PACKAGER"),
        "isize":       int(get("SIZE") or 0),
        "deps":        get_list("DEPENDS"),
        "optdeps":     get_list("OPTDEPENDS"),
        "conflicts":   get_list("CONFLICTS"),
        "provides":    get_list("PROVIDES"),
        "replaces":    get_list("REPLACES"),
        "license":     get_list("LICENSE"),
        "origin":      "pacman",
    }


def sync_from_pacman(
    local_db: Optional[LocalDB] = None,
    root: str = "/",
    verbose: bool = False,
) -> tuple[int, int, int]:
    """
    Scan /var/lib/pacman/local/ and create/update Sven LocalDB entries
    for any packages not already tracked by Sven.

    Entries created by this sync are marked with synced_only=True.
    They are QUERYABLE but not REMOVABLE by Sven.

    Returns:
        (added_count, updated_count, skipped_count)
    """
    if local_db is None:
        local_db = LocalDB()

    pacman_local = Path(root).resolve() / "var/lib/pacman/local"
    if not pacman_local.exists():
        if verbose:
            print(f"[sync] Pacman local DB not found: {pacman_local}")
        return (0, 0, 0)

    added = 0
    updated = 0
    skipped = 0

    for pkg_dir in pacman_local.iterdir():
        if not pkg_dir.is_dir():
            continue

        desc_path = pkg_dir / "desc"
        if not desc_path.exists():
            continue

        try:
            desc_text = desc_path.read_text(encoding="utf-8")
        except OSError:
            continue

        data = _parse_alpm_desc(desc_text)
        if not data["name"]:
            continue

        # If Sven already has this exact version, skip
        existing = local_db.get(data["name"])
        if existing and existing.version == data["version"]:
            skipped += 1
            continue

        # Build a Package object with synced_only flag
        # We store synced_only in the JSON metadata, not in the Package dataclass
        # (since Package doesn't have that field). We handle this in LocalDB._save_package.
        pkg = Package(
            name        = data["name"],
            version     = data["version"],
            desc        = data["desc"],
            url         = data["url"],
            repo        = data["origin"],
            origin      = data["origin"],
            arch        = data["arch"],
            isize       = data["isize"],
            packager    = data["packager"],
            builddate   = data["builddate"],
            deps        = data["deps"],
            optdeps     = data["optdeps"],
            conflicts   = data["conflicts"],
            provides    = data["provides"],
            replaces    = data["replaces"],
            license     = data["license"],
        )

        # Write to Sven's DB with synced_only marker
        local_db._save_package(pkg, synced_only=True)

        added += 1
        if verbose:
            print(f"[sync] Mirrored {pkg.name}-{pkg.version} (origin: pacman, synced_only)")

    return (added, updated, skipped)
