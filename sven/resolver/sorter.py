# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  resolver/sorter.py — topological sort for install order
# ============================================================

from typing import List, Dict, Set
from ..db.models import Package
from ..libsven import topo_sort as _c_topo_sort


def sort_dependencies(
    nodes: Dict[str, Package],
    edges: Dict[str, Set[str]]
) -> List[Package]:
    """
    Sort package installation order using C DFS topo sort.
    Handles circular dependencies by breaking cycles and warning.
    """
    names = list(nodes.keys())
    sorted_names, cycle_names = _c_topo_sort(names, edges)

    if cycle_names:
        from ..ui.output import print_warning
        print_warning(f"Circular dependency detected involving: {', '.join(cycle_names)}")
        print_warning("   Sven will attempt to break the cycle by installing implementation packages first.")

    return [nodes[name] for name in sorted_names if name in nodes]
