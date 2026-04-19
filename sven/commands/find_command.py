# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/find_command.py
# ============================================================
import sys
from ..db.sync_db import SyncDB
from ..db.aur_db import AURDB
from ..ui import print_info

def run(command: str):
    """
    Look for packages that provide the given command.
    """
    sync_db = SyncDB()
    aur_db  = AURDB()
    
    # 1. Direct Name Match (Most common for things like 'git', 'vim', etc.)
    pkg = sync_db.get(command)
    
    # 2. Virtual Provides Match
    # SyncDB.get already checks provides if direct name fails.
    
    # 3. Fuzzy search if not found
    if not pkg:
        potential = sync_db.search(command)
        if potential:
            # Pick first result if it's very relevant (e.g. name contains command)
            for p in potential:
                if command in p.name:
                    pkg = p
                    break
    
    # 4. Try AUR if official fails
    if not pkg:
        aur_results = aur_db.search(command)
        if aur_results:
            pkg = aur_results[0]

    if not pkg:
        # Silently fail if nothing found to avoid shell noise
        sys.exit(1)

    # 5. Output modern UI recommendation
    _print_recommendation(command, pkg)

def _print_recommendation(cmd: str, pkg):
    repo = f"\033[95m{pkg.repo}\033[0m"
    aur_tag = "" if pkg.repo != "aur" else f" [\033[96mAUR\033[0m]"
    
    # ── Calculate lengths for a clean box ────────────────
    # We use 50 chars inner width
    inner_w = 50
    line1 = f"{cmd} is not installed. It can be found in:"
    line2 = f"  {pkg.repo}/{pkg.name} ({pkg.version}){aur_tag}"
    line3 = f"Try running:  sudo sven install {pkg.name}"
    
    def pad(text, width):
        # strip ANSI for length calculation
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        plain = ansi_escape.sub('', text)
        return text + (" " * (width - len(plain)))

    print()
    print(f"   \033[1;96m╭{'─' * (inner_w + 2)}╮\033[0m")
    print(f"   \033[1;96m│\033[0m {pad(line1, inner_w)} \033[1;96m│\033[0m")
    print(f"   \033[1;96m│\033[0m {pad(line2, inner_w)} \033[1;96m│\033[0m")
    print(f"   \033[1;96m│\033[0m {pad('', inner_w)} \033[1;96m│\033[0m")
    print(f"   \033[1;96m│\033[0m {pad(line3, inner_w)} \033[1;96m│\033[0m")
    print(f"   \033[1;96m╰{'─' * (inner_w + 2)}╯\033[0m")
    print()
