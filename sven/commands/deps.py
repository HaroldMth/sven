# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/deps.py
# ============================================================
from ..resolver.graph import GraphBuilder
from ..ui import print_banner, print_section

def run(pkg_name: str, reverse: bool = False):
    print_banner()
    
    if reverse:
        print_section(f"Reverse dependencies for {pkg_name}:")
        print("   (Reverse dependency tree simulated)")
    else:
        print_section(f"Dependency tree for {pkg_name}:")
        graph = GraphBuilder().build([pkg_name])
        data = graph.get_graph_data()
        
        # Simple tree dump
        if pkg_name in data:
            for child in data[pkg_name]:
                print(f"   ├── {child}")
        else:
            print(f"   {pkg_name} has no dependencies.")
