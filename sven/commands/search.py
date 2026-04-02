# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/search.py
# ============================================================
from ..resolver.search import search_packages, SearchOptions
from ..ui import print_banner, print_section

def run(query: str):
    print_banner()
    print_section(f"Searching for '{query}'...")
    
    opts = SearchOptions(include_aur=True)
    results = search_packages(query, opts)
    
    if not results:
        print("   No packages found.")
        return
        
    for res in results:
        # Match Arch format
        repo = f"\033[95m{res.package.repo}\033[0m" # magenta config
        aur = "" if res.package.repo != "aur" else f" [\033[96mAUR\033[0m]"
        
        flags = ""
        # We'd check localDB for installed status here usually
        
        name = f"\033[1m{res.package.name}\033[0m"
        ver = f"\033[92m{res.package.version}\033[0m"
        desc = res.package.desc
        
        print(f"   {repo}/{name} {ver}{aur} {flags}")
        print(f"       {desc}")
