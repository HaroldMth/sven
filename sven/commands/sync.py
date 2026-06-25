# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/sync.py
# ============================================================
import sys
from ..db.sync_db import SyncDB
from ..ui import print_banner, print_section, print_success, print_warning, print_error

def run(**kwargs):
    print_banner()
    print_section("Synchronizing databases...")

    sync = SyncDB()
    results = sync.sync()

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
