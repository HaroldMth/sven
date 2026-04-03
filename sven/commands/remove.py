# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/remove.py
# ============================================================
import sys
from ..transaction import RemoveTransaction
from ..ui import print_banner, print_section, print_success, print_error, confirm

def run(packages: list[str], recursive: bool = False, force_protected: bool = False):
    print_banner()
    
    if not packages:
        print_error("No targets specified for removal.")
        sys.exit(1)
        
    print_section("Computing reverse dependencies...")
    
    if not confirm("Proceed with removal?"):
        print_error("Removal aborted by user.")
        sys.exit(0)
        
    tx = RemoveTransaction()
    
    if tx.execute(packages, force_protected=force_protected):

        for p in packages:
            print_success(f"{p} removed successfully")
    else:
        print_error("Removal failed.")
        sys.exit(1)
