# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  resolver/sorter.py — topological sort for install order
# ============================================================

import graphlib
from typing import List, Dict, Set
from ..db.models import Package
from ..exceptions import CircularDependencyError


def sort_dependencies(
    nodes: Dict[str, Package],
    edges: Dict[str, Set[str]]
) -> List[Package]:
    """
    Sort package installation order. 
    Handles circular dependencies by breaking them and warning.
    """
    # Use a custom DFS to handle cycles gracefully
    order = []
    visited = set()
    temp_stack = set()
    cycles_found = []

    def visit(name: str):
        if name in temp_stack:
            # Cycle detected!
            if name not in cycles_found:
                cycles_found.append(name)
            return
        if name in visited:
            return

        temp_stack.add(name)
        # Sort dependencies for deterministic order
        for dep in sorted(edges.get(name, set())):
            visit(dep)
        
        temp_stack.remove(name)
        visited.add(name)
        order.append(name)

    # Process all nodes
    for name in sorted(nodes.keys()):
        visit(name)

    if cycles_found:
        from ..ui.output import print_warning
        pkgs_in_cycle = ", ".join(cycles_found)
        print_warning(f"Circular dependency detected involving: {pkgs_in_cycle}")
        print_warning("   Sven will attempt to break the cycle by installing implementation packages first.")

    # Map names back to Package objects
    return [nodes[name] for name in order if name in nodes]
