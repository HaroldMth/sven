# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/list_cmd.py
# ============================================================
from ..db.local_db import LocalDB
from ..ui import print_banner, print_section

def run():
    print_banner()
    print_section("Installed Packages:")
    
    local = LocalDB()
    installed = local.list_installed()
    
    if not installed:
        print("   No packages installed.")
        return
        
    for p in sorted(installed):
        pkg = local.get(p)
        ver = pkg.version if pkg else "unknown"
        print(f"   {p} {ver}")
