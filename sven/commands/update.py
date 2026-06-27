# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/update.py
# ============================================================
import sys
from ..db.sync_db import SyncDB
from ..ui import print_banner, print_section, print_success, print_warning, print_error
from . import upgrade

def run(skip_aur: bool = False):
    print_banner()
    print_section("Syncing database catalogs...")

    db = SyncDB()
    results = db.sync()

    failed = [repo for repo, ok in results.items() if not ok]
    succeeded = [repo for repo, ok in results.items() if ok]

    if not succeeded:
        print_error(
            f"Synchronization failed — no repos reachable"
            + (f" ({', '.join(failed)})" if failed else "")
            + ". Skipping upgrade — nothing safe to upgrade against."
        )
        sys.exit(1)

    if failed:
        print_warning(f"Partially synchronized — {len(failed)} repo(s) failed: {', '.join(failed)}.")
    else:
        print_success("Repositories synchronized successfully.")

    # Trigger upgrade implicitly like `pacman -Syu`, but only against
    # databases that actually synced — never upgrade against stale/missing data.
    upgrade.run(skip_aur=skip_aur)
