# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/check_version.py
# ============================================================
import os
import re
from pathlib import Path
from ..db.local_db import LocalDB
from ..db.sync_db import SyncDB
from ..db.aur_db import AURDB
from ..constants import CACHE_PKGS
from ..ui import print_banner, print_section, print_info, print_error

def run(pkg_name: str):
    """
    Check versions of a package across local, sync, AUR, and cache.
    """
    print_banner()
    print_section(f"Version check for '{pkg_name}':")

    # 1. Local DB
    local = LocalDB()
    installed_pkg = local.get(pkg_name)
    installed_ver = installed_pkg.version if installed_pkg else "\033[90m(not installed)\033[0m"

    # 2. Sync DB
    sync = SyncDB()
    try:
        sync_pkg = sync.get(pkg_name)
        sync_ver = sync_pkg.version if sync_pkg else "\033[90m(not found)\033[0m"
    except Exception:
        sync_ver = "\033[91m(error reading sync db)\033[0m"

    # 3. AUR DB
    aur = AURDB()
    try:
        aur_pkg = aur.info(pkg_name)
        aur_ver = aur_pkg.version if aur_pkg else "\033[90m(not found)\033[0m"
    except Exception:
        aur_ver = "\033[91m(error reaching AUR)\033[0m"

    # 4. Local Cache
    cache_versions = []
    cache_path = Path(CACHE_PKGS)
    if cache_path.exists():
        # Match filenames like pkgname-1.2.3-1-x86_64.pkg.tar.zst
        # Arch format: name-version-rel-arch.pkg.tar.zst
        # We try to extract version-rel
        for f in cache_path.iterdir():
            if f.name.startswith(f"{pkg_name}-") and any(f.name.endswith(ext) for ext in [".pkg.tar.zst", ".pkg.tar.xz"]):
                # Rough split: strip arch and extension
                # e.g. neovim-0.9.5-1-x86_64.pkg.tar.zst -> neovim-0.9.5-1
                ver_part = f.name
                for ext in [".pkg.tar.zst", ".pkg.tar.xz"]:
                    if ver_part.endswith(ext):
                        ver_part = ver_part[:-len(ext)]
                        break
                
                # Strip arch (e.g. -x86_64 or -any)
                if ver_part.endswith("-x86_64"):
                    ver_part = ver_part[:-7]
                elif ver_part.endswith("-any"):
                    ver_part = ver_part[:-4]
                
                # Strip name-
                if ver_part.startswith(f"{pkg_name}-"):
                    version = ver_part[len(pkg_name)+1:]
                    if version:
                        cache_versions.append(version)

    print_info(f"Installed    : {installed_ver}")
    print_info(f"Official     : {sync_ver}")
    print_info(f"AUR          : {aur_ver}")
    
    if cache_versions:
        # Sort versions (unique)
        unique_versions = sorted(list(set(cache_versions)))
        print_info(f"Local Cache  : {', '.join(unique_versions)}")
    else:
        print_info(f"Local Cache  : \033[90m(none)\033[0m")
    
    print()
