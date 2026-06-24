"""Derive a topic's algorithm family from its title/type when not explicitly set.

The property gate, executor, and telemetry all dispatch on `topic_family`, but topics frequently reach
gen_foundation with it EMPTY (the lessons route passes only id/title/topic_type). An empty family means
the MST/sort/traversal invariant checks never match -> wrong answers (the Kruskal/Prim MSTs) sail
through. This maps the title to a family string that CONTAINS the keywords the property checks look for
(`mst`, `kruskal`, `prim`, `sort`, `bfs`, ...), so deriving "graph_mst_kruskal" makes the gate fire.

Pure, keyword-based, conservative: returns "" when nothing matches (never guesses a wrong family).
"""
from __future__ import annotations

# (keywords in the title, family string to assign). Order matters — first match wins.
_RULES: list[tuple[tuple[str, ...], str]] = [
    (("kruskal", "prim", "minimum spanning", "spanning tree", "mst"), "graph_mst"),
    (("dijkstra", "bellman-ford", "bellman ford", "shortest path", "a* search", "a-star"), "graph_shortest_path"),
    (("topological sort", "topological ordering", "topo sort"), "graph_topological"),
    (("breadth-first", "breadth first", "bfs"), "graph_traversal_bfs"),
    (("depth-first", "depth first", "dfs"), "graph_traversal_dfs"),
    (("binary search tree", "bst"), "tree_bst"),
    (("binary search",), "array_binary_search"),
    (("quicksort", "quick sort", "merge sort", "mergesort", "heap sort", "heapsort",
      "insertion sort", "selection sort", "bubble sort", "radix sort", "counting sort", "sorting", "sort"),
     "array_sort"),
    (("min-heap", "max-heap", "binary heap", "priority queue", "heapify"), "heap"),
    (("union-find", "union find", "disjoint set"), "graph_mst"),  # union-find is taught with Kruskal/MST
]


def derive_topic_family(title: str | None, topic_type: str | None = "", existing: str | None = "") -> str:
    """Return an explicit family if given, else infer one from the title, else "" (no guess)."""
    if existing and existing.strip():
        return existing.strip()
    text = (title or "").lower()
    for keywords, family in _RULES:
        if any(k in text for k in keywords):
            return family
    return ""
