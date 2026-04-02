# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  resolver/file_conflict.py — file-level conflict detection
# ============================================================
#
#  Before extracting a package archive, check every file against
#  the local DB to ensure no file is already owned by another
#  package. Prevents silent overwrites and system corruption.
# ============================================================

import tarfile
from pathlib import Path
from typing import Optional

from ..db.local_db import LocalDB
from ..db.models import Package
from ..exceptions import FileConflictError


def get_package_file_list(archive_path: str) -> list[str]:
    """
    Extract the file list from a .pkg.tar.zst archive.
    Returns a list of file paths (relative, no leading /).
    """
    files = []
    try:
        with tarfile.open(archive_path, "r:*") as tar:
            for member in tar.getmembers():
                name = member.name
                # Skip metadata files
                if name.startswith("."):
                    continue
                # Normalise: strip leading ./ and /
                name = name.lstrip("./")
                if name:
                    files.append(name)
    except (tarfile.TarError, OSError):
        pass
    return files


def check_file_conflicts(
    pkg: Package,
    archive_path: str,
    local_db: LocalDB,
    force: bool = False,
) -> list[dict]:
    """
    Check if any file in the package archive conflicts with
    files owned by already-installed packages.

    Args:
        pkg: The package being installed
        archive_path: Path to the .pkg.tar.zst file
        local_db: The local installed package database
        force: If True, report conflicts but don't raise

    Returns:
        List of conflict dicts: [{file, owner, new_pkg}, ...]

    Raises:
        FileConflictError if conflicts are found and force=False
    """
    new_files = get_package_file_list(archive_path)
    if not new_files:
        return []

    # Build a reverse index: file → owning package
    # This is expensive but necessary for correctness
    file_owners = _build_file_ownership_map(local_db, exclude_pkg=pkg.name)

    conflicts = []
    for filepath in new_files:
        owner = file_owners.get(filepath)
        if owner and owner != pkg.name:
            conflicts.append({
                "file": filepath,
                "owner": owner,
                "new_pkg": pkg.name,
            })

    if conflicts and not force:
        # Report the first conflict as an error
        first = conflicts[0]
        raise FileConflictError(
            filename=first["file"],
            owner_pkg=first["owner"],
            new_pkg=first["new_pkg"],
        )

    return conflicts


def _build_file_ownership_map(
    local_db: LocalDB,
    exclude_pkg: Optional[str] = None,
) -> dict[str, str]:
    """
    Build a dict mapping every installed file to its owning package.
    Skips the exclude_pkg (used during upgrades where the same
    package is being replaced).
    """
    ownership = {}

    for pkg in local_db.all_packages():
        if exclude_pkg and pkg.name == exclude_pkg:
            continue

        files = local_db.get_files(pkg.name)
        for f in files:
            # Normalise path
            f = f.lstrip("/")
            ownership[f] = pkg.name

    return ownership


def check_internal_conflicts(packages: list[Package], archives: dict[str, str]) -> list[dict]:
    """
    Check if multiple NEW packages being installed contain
    the same files (conflict between packages in the same transaction).

    Args:
        packages: List of packages being installed
        archives: Dict of {pkg_name: archive_path}

    Returns:
        List of conflict dicts
    """
    file_to_pkg: dict[str, str] = {}
    conflicts = []

    for pkg in packages:
        archive = archives.get(pkg.name)
        if not archive:
            continue

        files = get_package_file_list(archive)
        for filepath in files:
            if filepath in file_to_pkg:
                other = file_to_pkg[filepath]
                if other != pkg.name:
                    conflicts.append({
                        "file": filepath,
                        "owner": other,
                        "new_pkg": pkg.name,
                    })
            else:
                file_to_pkg[filepath] = pkg.name

    return conflicts
