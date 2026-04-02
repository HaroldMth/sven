# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/rollback.py
# ============================================================
import sys
from ..installer.rollback import RollbackManager
from ..ui import print_banner, print_section, confirm, print_success, print_error
from ..exceptions import RollbackError

def run(snapshot_id: str):
    print_banner()
    print_section(f"Inititating System Rollback to {snapshot_id}")
    
    if not confirm("Are you sure? This will reverse the local database and filesystem to past state.", default=False):
        sys.exit(0)
        
    mgr = RollbackManager()
    try:
        mgr.restore(snapshot_id)
        print_success("System rollback complete.")
    except RollbackError as e:
        print_error(str(e))
        sys.exit(1)
