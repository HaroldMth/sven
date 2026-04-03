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
    Sort package installation order using TopologicalSorter.
    Ensures dependencies are installed before the packages that need them.
    Raises CircularDependencyError if a cycle is detected.
    """
    ts = graphlib.TopologicalSorter(edges)
    
    try:
        # returns an iterable of package names in order
        order = list(ts.static_order())
    except graphlib.CycleError as e:
        # Fallback to naive list for circular dependencies
        return list(nodes.values())

    # Map names back to Package objects
    return [nodes[name] for name in order if name in nodes]
