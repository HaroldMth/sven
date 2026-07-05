# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/sync.py
# ============================================================
import sys
from ..db.sync_db import SyncDB
from ..ui import print_banner, print_section, print_success, print_warning, print_error

def run(force: bool = False, from_pacman: bool = False, **kwargs):
    print_banner()
    print_section("Synchronizing databases...")

    sync = SyncDB()
    results = sync.sync(force=force)

    failed = [repo for repo, ok in results.items() if not ok]
    succeeded = [repo for repo, ok in results.items() if ok]

    if not results:
        print_error("No repositories configured to sync.")
        sys.exit(1)

    if failed and not succeeded:
        print_error(
            f"Synchronization failed — all {len(failed)} repo(s) unreachable: "
            f"{', '.join(failed)}. Check your network/mirror and try again."
        )
        sys.exit(1)

    if failed:
        print_warning(
            f"Partially synchronized — {len(failed)} repo(s) failed: {', '.join(failed)}. "
            f"{len(succeeded)} succeeded: {', '.join(succeeded)}."
        )
        sys.exit(1)

    print_success("Databases synchronized successfully.")

    if from_pacman:
        print_section("Syncing pacman-managed packages into Sven DB...")
        from ..db.pacman_sync import sync_from_pacman
        from ..db.local_db import LocalDB
        added, updated, skipped = sync_from_pacman(local_db=LocalDB(), verbose=True)
        print_success(f"Pacman sync complete — {added} added, {updated} updated, {skipped} already known.")
