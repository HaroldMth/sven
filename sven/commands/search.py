# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/search.py
# ============================================================
from ..resolver.search import search as search_packages
from ..db.sync_db import SyncDB
from ..db.aur_db import AURDB
from ..ui import print_banner, print_section

def run(query: str, aur_only: bool = False, official_only: bool = False, installed_only: bool = False):
    print_banner()
    print_section(f"Searching for '{query}'...")

    sync_db = SyncDB()
    aur_db  = AURDB()

    results = search_packages(
        query,
        sync_db=sync_db,
        aur_db=aur_db,
        official_only=official_only,
        aur_only=aur_only,
        installed_only=installed_only,
    )

    if not results:
        print("   No packages found.")
        return

    for pkg in results:
        repo = f"\033[95m{pkg.repo}\033[0m"
        aur_tag = "" if pkg.repo != "aur" else f" [\033[96mAUR\033[0m]"

        name = f"\033[1m{pkg.name}\033[0m"
        ver  = f"\033[92m{pkg.version}\033[0m"
        desc = pkg.desc

        print(f"   {repo}/{name} {ver}{aur_tag}")
        print(f"       {desc}")
