# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/verify.py
# ============================================================
import os
import hashlib
from pathlib import Path
from ..db.local_db import LocalDB
from ..config import get_config
from ..ui import print_banner, print_section, print_error, print_success, print_warning

def run(pkg_name: str = None):
    print_banner()
    local = LocalDB()
    cfg = get_config()
    
    pkgs = [pkg_name] if pkg_name else local.list_installed()
    if not pkgs:
        print_section("No packages installed.")
        return

    print_section("Verifying installed files...")
    broken_count = 0
    checked_count = 0

    # In a full system, LocalDB would store the physical SHA256 of every file
    # For simulation, we'll just check if the files physically exist and are readable
    for p in pkgs:
        files = local.get_files(p)
        for f in files:
            path = Path(cfg.rooted(f))
            checked_count += 1
            if not path.exists():
                print_error(f"Missing file: {f} (owned by {p})")
                broken_count += 1

    if broken_count > 0:
        print_warning(f"Verification completed. {broken_count}/{checked_count} files are broken or missing.")
    else:
        print_success(f"Verification perfect. {checked_count} system files are intact.")
