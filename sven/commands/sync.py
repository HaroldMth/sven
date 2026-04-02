# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/sync.py
# ============================================================
from ..db.sync_db import SyncDB
from ..ui import print_banner, print_section, print_success

def run(**kwargs):
    print_banner()
    print_section("Synchronizing databases...")

    sync = SyncDB()
    sync.sync()

    print_success("Databases synchronized successfully.")
