# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/info.py
# ============================================================
import sys
from ..db.local_db import LocalDB
from ..db.sync_db import SyncDB
from ..db.aur_db import AURDB
from ..ui import print_banner, print_error, print_section

def run(pkg_name: str):
    print_banner()
    print_section(f"Information for '{pkg_name}':")
    
    local = LocalDB()
    pkg = local.get(pkg_name)
    installed = bool(pkg)
    
    if not pkg:
        sync = SyncDB()
        pkg = sync.get(pkg_name)
    
    if not pkg:
        aur = AURDB()
        pkg = aur.get(pkg_name)
        
    if not pkg:
        print_error(f"Package '{pkg_name}' not found anywhere.")
        sys.exit(1)
        
    print(f"   Name           : {pkg.name}")
    print(f"   Version        : {pkg.version}")
    print(f"   Description    : {pkg.desc}")
    print(f"   URL            : {pkg.url}")
    print(f"   Repository     : {pkg.repo}")
    print(f"   Depends On     : {', '.join(pkg.deps) or 'None'}")
    print(f"   Make Depends   : {', '.join(pkg.makedeps) or 'None'}")
    print(f"   Opt Depends    : {', '.join(pkg.optdeps) or 'None'}")
    print(f"   Conflicts      : {', '.join(pkg.conflicts) or 'None'}")
    print(f"   Provides       : {', '.join(pkg.provides) or 'None'}")
    print(f"   Installed      : {'Yes' if installed else 'No'}")
    
    if installed:
        fs = local.get_files(pkg_name)
        print(f"   Files owned    : {len(fs)}")
