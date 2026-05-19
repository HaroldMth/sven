# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/upgrade.py
# ============================================================
import sys
from ..transaction import UpgradeTransaction
from ..ui import print_banner, print_section, print_success, print_error, confirm, print_info
from ..ui.prompt import show_package_list

def run(packages: list[str] = None, force_protected: bool = False, verbose: bool = False):
    print_banner()
    print_section("Checking for upgrades...")
    
    tx = UpgradeTransaction(explicit=False, verbose=verbose)
    resolved = tx.resolve(packages, force_protected=force_protected)
    
    if not resolved:
        print_success("Everything is up to date.")
        return
        
    # Organize into categories
    to_build = [p for p in resolved if p.origin == "aur"]
    
    from ..constants import CACHE_PKGS
    from pathlib import Path
    cache_path = Path(CACHE_PKGS)
    
    cached_pkgs = []
    download_pkgs = []
    for p in resolved:
        if p.origin == "aur":
            continue
        p_path = cache_path / p.filename
        if p_path.exists() and p_path.stat().st_size > 0:
            cached_pkgs.append(p)
        else:
            download_pkgs.append(p)
            
    total_dl_bytes = sum(p.size for p in download_pkgs)
    total_dl_mib = total_dl_bytes / 1024 / 1024
    
    print()
    print(f"   \033[1mTransaction Summary\033[0m")
    print(f"   ├─ Re-using Cached   : {len(cached_pkgs)} packages")
    print(f"   ├─ To Download       : {len(download_pkgs)} ({total_dl_mib:.2f} MiB)")
    print(f"   └─ To Build (AUR)    : {len(to_build)}")
    print()

    # Calculate sizes
    total_dl = sum(p.size for p in resolved)
    total_inst = sum(p.isize for p in resolved)

    show_package_list(resolved, total_dl, total_inst)
    print_info(
        f"Ready to upgrade {len(resolved)} package(s). "
        "A rollback snapshot is created automatically before any changes."
    )

    if not confirm("Proceed with upgrade?"):
        print_error("Upgrade aborted by user.")
        sys.exit(0)
        
    if tx.execute_resolved(resolved, force_protected=force_protected, install_targets=packages):
        print_success("System upgraded successfully")
    else:
        print_error("Upgrade failed.")
        sys.exit(1)
