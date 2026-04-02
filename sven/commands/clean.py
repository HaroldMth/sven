# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/clean.py
# ============================================================
import shutil
from pathlib import Path
from ..config import get_config
from ..builder.aur_cache import AURCache
from ..ui import print_banner, print_section, print_success, confirm

def run(all_cache: bool = False, aur_only: bool = False):
    print_banner()
    
    cfg = get_config()
    core_cache = Path(cfg.rooted("/var/cache/sven/pkgs"))
    
    if aur_only:
        print_section("Cleaning AUR cache...")
        if confirm("Delete all cached AUR builds?"):
            aur = AURCache()
            aur.clean()
            print_success("AUR cache cleaned.")
        return

    print_section("Cleaning all package caches...")
    if confirm("Delete all cached package files?"):
        
        # Clean official
        if core_cache.exists():
            for f in core_cache.iterdir():
                if f.is_file():
                    f.unlink()
        
        # Clean AUR
        aur = AURCache()
        aur.clean()
        
        print_success("Package caches cleaned.")
