"""Topic classifier v2 — extends the legacy course_type_classifier with
visual_domain inference.

Doesn't replace the legacy classifier (`enrich_topic_with_course_type`
in course_type_classifier.py). Instead, this module post-processes a
topic with topic_type already set, and infers:
  - visual_domain
  - visual_mode_hint

These get attached to the topic for the v2 pipeline to consume.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.visual_ontology_v2 import (
    DOMAIN_TO_BASE_TYPE,
    DOMAIN_TO_DEFAULT_MODE,
    VISUAL_DOMAINS,
)


# ---------------------------------------------------------------------------
# Keyword-based domain inference
# ---------------------------------------------------------------------------

# Ordered: first match wins. Stricter patterns first.
_DOMAIN_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tree", (
        "bst", "binary search tree", "binary tree", "n-ary tree", "heap",
        "trie", "tree traversal", "inorder", "preorder", "postorder",
        "level order", "level-order", "avl tree", "red black tree",
        "red-black tree", "segment tree", "fenwick tree", "tree dp",
    )),
    ("graph", (
        "graph traversal", "bfs", "dfs", "breadth-first", "depth-first",
        "breadth first", "depth first", "shortest path", "dijkstra",
        "bellman-ford", "bellman ford", "floyd-warshall", "floyd warshall",
        "minimum spanning tree", "mst", "prim", "kruskal", "topological sort",
        "topological", "strongly connected", "scc", "cycle detection",
        "adjacency list",
    )),
    ("linked_list", (
        "linked list", "singly linked", "doubly linked", "circular linked",
        "linked-list",
    )),
    ("array", (
        "binary search", "sliding window", "two pointer", "two pointers",
        "two-pointer", "prefix sum", "subarray", "kadane",
        "merge sort", "quicksort", "quick sort", "heap sort", "insertion sort",
        "bubble sort", "selection sort", "radix sort", "counting sort",
        "array rotation", "in-place",
    )),
    ("string", (
        "string matching", "kmp", "rabin-karp", "rabin karp",
        "longest substring", "palindrome", "anagram", "string manipulation",
        "rolling hash",
    )),
    ("matrix", (
        "matrix", "dp table", "dynamic programming table", "2d dp",
        "longest common subsequence", "lcs", "edit distance", "knapsack",
        "adjacency matrix", "rotate matrix", "spiral matrix", "k-map",
        "karnaugh", "confusion matrix",
    )),
    ("table", (
        "comparison table", "truth table", "decision table", "variable trace",
        "sql table",
    )),
    ("memory", (
        "stack frame", "call stack", "heap allocation", "pointer reference",
        "garbage collection", "virtual memory", "page table", "cache",
        "buffer overflow", "memory layout",
    )),
    ("code", (
        "code walkthrough", "implementation", "coding", "implement in",
        "write the function", "code this", "python implementation",
        "java implementation",
    )),
    ("coordinate_math", (
        "normal distribution", "loss curve", "regression", "polynomial graph",
        "derivative", "integral", "convergence", "roc curve", "big-o growth",
        "big o growth", "asymptotic", "function graph",
    )),
    ("geometry", (
        "triangle", "circle geometry", "vector projection", "3d solid",
        "related rates", "optimization geometry", "trigonometry",
    )),
    ("formula", (
        "bayes theorem", "bayes rule", "law of cosines", "law of sines",
        "quadratic formula", "binomial", "recurrence relation", "formula derivation",
        "algebraic transformation", "calculus derivation",
    )),
    ("timeline_protocol", (
        "tcp handshake", "tcp/ip", "http request", "oauth", "thread schedule",
        "message passing", "race condition", "lock acquisition",
        "transaction", "protocol",
    )),
    ("set_logic", (
        "venn diagram", "set union", "set intersection", "set complement",
        "sample space", "probability region", "boolean algebra",
    )),
    ("real_world", (
        "analogy", "real world", "everyday", "intuition for", "metaphor",
    )),
)


def infer_visual_domain(topic_title: str, topic_summary: str = "") -> str:
    """Infer visual_domain from topic title + summary.

    Returns one of VISUAL_DOMAINS; "generic" if no match.
    """
    text = f"{topic_title} {topic_summary}".lower()
    for domain, keywords in _DOMAIN_KEYWORDS:
        for keyword in keywords:
            if keyword in text:
                return domain
    return "generic"


def infer_visual_mode_hint(visual_domain: str, topic_title: str = "") -> str:
    """Suggest a default mode under the domain's base_type.

    Topic-specific overrides (e.g. binary_search → binary_search_range mode)
    are applied here; otherwise defaults from DOMAIN_TO_DEFAULT_MODE.
    """
    text = topic_title.lower()

    # Topic-specific mode overrides
    if visual_domain == "array":
        if "binary search" in text:
            return "binary_search_range"
        if "sliding window" in text:
            return "sliding_window"
        if "two pointer" in text or "two-pointer" in text:
            return "two_pointer"
        if "merge sort" in text or "quicksort" in text or "quick sort" in text:
            return "sorting_pass"
        if "prefix sum" in text:
            return "prefix_sum"
    elif visual_domain == "graph":
        if "bfs" in text or "breadth" in text:
            return "graph_network"  # mode stays; BFS is shown by frontier semantics
        if "dfs" in text or "depth" in text:
            return "graph_network"
        if "mst" in text or "prim" in text or "kruskal" in text:
            return "graph_network"
        if "shortest path" in text or "dijkstra" in text:
            return "graph_network"
        if "topological" in text:
            return "dependency_graph"
    elif visual_domain == "matrix":
        if "dp" in text or "dynamic programming" in text:
            return "dp_table"
        if "adjacency" in text:
            return "adjacency_matrix"
        if "k-map" in text or "karnaugh" in text:
            return "karnaugh_map"
        if "confusion matrix" in text:
            return "confusion_matrix"
    elif visual_domain == "coordinate_math":
        if "loss" in text:
            return "loss_curve"
        if "distribution" in text or "normal" in text:
            return "distribution_curve"
        if "regression" in text:
            return "regression_plot"
        if "roc" in text:
            return "roc_curve"
        if "growth" in text or "big-o" in text or "big o" in text:
            return "runtime_growth"

    return DOMAIN_TO_DEFAULT_MODE.get(visual_domain, "topic_motivation")


def classify_topic_v2(
    topic_title: str,
    topic_summary: str,
    topic_type: str,
    knowledge_level: int | None = None,
) -> dict[str, Any]:
    """Produce the v2 classification dict matching TOPIC_CLASSIFICATION_V2_SCHEMA.

    Doesn't make an LLM call — pure keyword routing. The legacy classifier
    handles topic_type; we just add visual_domain on top.
    """
    visual_domain = infer_visual_domain(topic_title, topic_summary)
    visual_mode_hint = infer_visual_mode_hint(visual_domain, topic_title)
    return {
        "topic_type": topic_type,
        "secondary_topic_types": [],
        "knowledge_level": knowledge_level,
        "visual_domain": visual_domain,
        "visual_mode_hint": visual_mode_hint,
        "reason": (
            f"Inferred visual_domain={visual_domain} (mode hint "
            f"{visual_mode_hint}) from topic keywords."
        ),
    }


def base_type_for_classification(classification: dict[str, Any]) -> str:
    return DOMAIN_TO_BASE_TYPE.get(
        str(classification.get("visual_domain") or "generic"),
        "image_real_world_illustration",
    )
