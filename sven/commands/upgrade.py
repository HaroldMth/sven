# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/upgrade.py
# ============================================================
import sys
from ..transaction import UpgradeTransaction
from ..ui import print_banner, print_section, print_success, print_error, confirm

def run(packages: list[str] = None, force_protected: bool = False):
    print_banner()
    print_section("Checking for upgrades...")
    
    if not confirm("Proceed with upgrade?"):
        print_error("Upgrade aborted by user.")
        sys.exit(0)
        
    tx = UpgradeTransaction()
    
    if tx.execute(packages, force_protected=force_protected):

        print_success("System upgraded successfully")
    else:
        print_error("Upgrade failed.")
        sys.exit(1)
