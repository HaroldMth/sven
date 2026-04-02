# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/snapshots.py
# ============================================================
from ..installer.rollback import RollbackManager
from ..ui import print_banner, print_section

def run():
    print_banner()
    print_section("System Rollback Snapshots:")
    
    mgr = RollbackManager()
    snaps = mgr.list_snapshots()
    
    if not snaps:
        print("   No snapshots available.")
        return
        
    for s in snaps:
        print(f"   {s['id']}  [{s['time']}]")
