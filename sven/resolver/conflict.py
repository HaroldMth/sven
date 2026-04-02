# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  resolver/conflict.py — conflict detection and resolution
# ============================================================

from typing import List
from ..db.models import Package
from ..db.local_db import LocalDB
from ..exceptions import DependencyConflictError


def check_conflicts(
    to_install: List[Package],
    local_db: LocalDB
):
    """
    Check for package conflicts.
    A conflict occurs if:
    1. A new package conflicts with an already installed package.
    2. Two new packages conflict with each other.
    3. A new package replaces an already installed one (not a conflict, but an upgrade/replacement).
    """
    # ── Installed Packages ──
    installed = local_db.all_packages()
    
    # Names being installed
    new_names = {p.name for p in to_install}
    
    for pkg in to_install:
        # Check against installed packages
        for inst in installed:
            # Skip if the new package is an upgrade of the installed one
            if pkg.name == inst.name:
                continue
            
            # Skip if the new package REPLACES the installed one
            if inst.name in pkg.replaces:
                continue
            
            # Check %CONFLICTS% field
            if inst.name in pkg.conflicts:
                raise DependencyConflictError(pkg.name, inst.name)
            
            # Check if installed package conflicts with the new one
            if pkg.name in inst.conflicts:
                raise DependencyConflictError(inst.name, pkg.name)

        # Check against other new packages
        for other in to_install:
            if pkg.name == other.name:
                continue
            
            if other.name in pkg.conflicts:
                raise DependencyConflictError(pkg.name, other.name)
            
            # Check virtual provides as well
            for prov in other.provides:
                # Strip versions from provides
                virt_name = prov.split(">")[0].split("<")[0].split("=")[0].strip()
                if virt_name in pkg.conflicts:
                    raise DependencyConflictError(pkg.name, other.name)
