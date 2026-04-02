# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/mirror.py
# ============================================================
from ..downloader.mirror import MirrorManager
from ..ui import print_banner, print_section, print_info

def run(benchmark: bool = False):
    print_banner()
    mgr = MirrorManager()
    
    if benchmark:
        print_section("Benchmarking mirrors...")
        ordered = mgr.benchmark_all()
        for idx, ms in enumerate(ordered):
            speed = f"{ms['ping_ms']}ms" if ms['ping_ms'] != float('inf') else "offline"
            print(f"   [{idx+1}] {ms['url']} ({speed})")
    else:
        print_section("Active Mirrors:")
        raw = mgr.mirrors
        for r in raw:
            print_info(f"{r}")
