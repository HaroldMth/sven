# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  resolver/search.py — unified official + AUR search
# ============================================================

from typing import Optional
from ..db.sync_db import SyncDB
from ..db.aur_db import AURDB
from ..db.local_db import LocalDB
from ..db.models import Package


def search(
    query: str,
    sync_db: SyncDB,
    aur_db: AURDB,
    local_db: Optional[LocalDB] = None,
    official_only: bool = False,
    aur_only: bool = False,
    installed_only: bool = False
) -> list[Package]:
    """
    Search official repositories and AUR.
    Returns a deduplicated list of Package objects.
    Sorted by relevance: exact match -> starts with -> contains.
    """
    official_results = []
    aur_results      = []

    if not aur_only:
        official_results = sync_db.search(query)

    if not official_only:
        # Search AUR by name/desc (default)
        aur_results = aur_db.search(query)

    # Combined results
    results = []
    seen    = set()

    # Add official first
    for pkg in official_results:
        if pkg.name not in seen:
            results.append(pkg)
            seen.add(pkg.name)

    # Add AUR if not already in official
    for pkg in aur_results:
        if pkg.name not in seen:
            results.append(pkg)
            seen.add(pkg.name)

    # Filter by installed if requested
    if installed_only and local_db:
        # Just check if the package name is in LocalDB
        results = [p for p in results if local_db.is_installed(p.name)]

    # Final sort (SyncDB search handles its own internal sorting,
    # and AURDB handles its own popularity sorting, but we merge them).
    # Re-applying a global sort ensures the best user experience.
    q = query.lower()

    def sort_key(p: Package):
        name = p.name.lower()
        if name == q: return 0
        if name.startswith(q): return 1
        return 2

    # Stabilize by sorting by name/origin as well
    results.sort(key=lambda p: (sort_key(p), p.name, p.origin))

    return results
