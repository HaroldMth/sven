# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  db/db_version.py — database format versioning
# ============================================================
#
#  Stores a DB_FORMAT_VERSION alongside each synced DB.
#  On sync, validates the DB structure before loading.
#  If format is unrecognised → warning instead of crash.
# ============================================================

import json
from pathlib import Path

from ..constants import DB_BASE


DB_FORMAT_VERSION = 1
VERSION_FILE = f"{DB_BASE}/db_version.json"


def write_db_version(version: int = DB_FORMAT_VERSION):
    """Write the current DB format version to disk."""
    data = {
        "format_version": version,
        "manager": "sven",
        "note": "Do not edit. Used for DB migration checks.",
    }
    path = Path(VERSION_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def read_db_version() -> int:
    """
    Read the DB format version from disk.
    Returns 0 if the file doesn't exist (fresh install).
    Returns -1 if the file is corrupt/unreadable.
    """
    path = Path(VERSION_FILE)
    if not path.exists():
        return 0

    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("format_version", -1)
    except (json.JSONDecodeError, OSError):
        return -1


def check_db_version() -> tuple[bool, str]:
    """
    Check if the DB format is compatible with this version of sven.

    Returns:
        (compatible, message)
    """
    on_disk = read_db_version()

    if on_disk == 0:
        # Fresh install — write current version
        write_db_version()
        return True, "Fresh install — DB initialised."

    if on_disk == -1:
        return False, (
            "DB version file is corrupt. Run 'sven sync --force' "
            "to rebuild the database."
        )

    if on_disk == DB_FORMAT_VERSION:
        return True, "DB format is up to date."

    if on_disk > DB_FORMAT_VERSION:
        return False, (
            f"DB format version {on_disk} is newer than this version "
            f"of sven supports ({DB_FORMAT_VERSION}). "
            f"Update sven or run 'sven sync --force'."
        )

    if on_disk < DB_FORMAT_VERSION:
        # Future: run migrations here
        return False, (
            f"DB format version {on_disk} is outdated (current: "
            f"{DB_FORMAT_VERSION}). Run 'sven sync --force' to upgrade."
        )

    return True, "OK"
