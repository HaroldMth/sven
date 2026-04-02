# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/update.py
# ============================================================
import sys
from ..db.sync_db import SyncDB
from ..ui import print_banner, print_section, print_success
from . import upgrade

def run():
    print_banner()
    print_section("Syncing database catalogs...")
    
    # SyncDB sync
    db = SyncDB()
    db.sync()
    
    print_success("Repositories synchronized successfully.")
    
    # Trigger upgrade implicitly like `pacman -Syu`
    upgrade.run()
