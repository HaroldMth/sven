# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  ui/graph_render.py — ANSI dependency tree visualizer
# ============================================================

import sys
from typing import Dict, Set, List, Optional
from ..db.models import Package

def render_dependency_tree(
    targets: List[str],
    edges: Dict[str, Set[str]],
    nodes: Dict[str, Package],
    prefix: str = "   ",
):
    """
    Prints a beautiful ANSI tree of dependencies.
    """
    print(f"{prefix}\033[1;36mDependency Tree\033[0m")
    
    seen = set()

    def _render_node(name: str, level_prefix: str, is_last: bool):
        pkg = nodes.get(name)
        if not pkg:
            # Could be a package that was already installed and skipped
            # but still in the edges.
            return

        connector = "└── " if is_last else "├── "
        
        # Color based on origin
        color = "\033[35m" if pkg.origin == "aur" else "\033[34m"
        meta = f" (\033[90m{pkg.version}\033[0m)"
        
        print(f"{level_prefix}{connector}{color}{name}\033[0m{meta}")
        
        if name in seen:
            # Avoid infinite recursion and clutter
            # (though Sven's graph is a DAG, we still want to avoid multi-printing)
            return
        seen.add(name)

        child_deps = sorted(list(edges.get(name, set())))
        new_prefix = level_prefix + ("    " if is_last else "│   ")
        
        for i, child in enumerate(child_deps):
            _render_node(child, new_prefix, i == len(child_deps) - 1)

    for i, target in enumerate(sorted(targets)):
        _render_node(target, prefix, i == len(targets) - 1)
    print()
