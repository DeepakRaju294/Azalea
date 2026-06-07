from __future__ import annotations

import re
from typing import Any


AssumptionRule = dict[str, Any]


def normalize_assumption_phrase(value: Any) -> str:
    """Normalize text for lightweight topic matching and deduping."""
    return " ".join(re.sub(r"[^\w\s]", " ", str(value or "")).lower().split())


ASSUMPTION_RULES: list[AssumptionRule] = [
    {
        "id": "bst_traversal",
        "match_any": [
            "bst traversal",
            "bst traversals",
            "binary search tree traversal",
            "binary search tree traversals",
            "inorder traversal",
            "preorder traversal",
            "postorder traversal",
            "level order traversal",
            "level-order traversal",
        ],
        "assumed_prerequisites": [
            "binary search tree",
            "BST",
            "node",
            "root",
            "left child",
            "right child",
            "subtree",
            "leaf node",
            "BST ordering property",
        ],
        "do_not_reteach": [
            "what a node is",
            "what a root is",
            "what a subtree is",
            "how BST ordering works in general",
            "basic binary tree structure",
        ],
    },
    {
        "id": "binary_tree_traversal",
        "match_any": [
            "binary tree traversal",
            "tree traversal",
            "inorder traversal",
            "preorder traversal",
            "postorder traversal",
            "level order traversal",
            "level-order traversal",
        ],
        "assumed_prerequisites": [
            "binary tree",
            "node",
            "root",
            "left child",
            "right child",
            "subtree",
            "leaf node",
        ],
        "do_not_reteach": [
            "what a node is",
            "what a root is",
            "what a subtree is",
            "basic binary tree structure",
        ],
    },
    {
        "id": "graph_traversal",
        "match_any": [
            "graph traversal",
            "breadth first search",
            "breadth-first search",
            "bfs",
            "depth first search",
            "depth-first search",
            "dfs",
        ],
        "assumed_prerequisites": [
            "graph",
            "vertex",
            "node",
            "edge",
            "neighbor",
            "path",
            "directed graph",
            "undirected graph",
        ],
        "do_not_reteach": [
            "what a graph is",
            "what vertices and edges are",
            "basic graph terminology",
        ],
    },
    {
        "id": "minimum_spanning_tree",
        "match_any": [
            "minimum spanning tree",
            "mst",
            "prim",
            "prim's algorithm",
            "kruskal",
            "kruskal's algorithm",
        ],
        "assumed_prerequisites": [
            "graph",
            "vertex",
            "edge",
            "weighted graph",
            "undirected graph",
            "connected graph",
            "cycle",
            "path",
        ],
        "do_not_reteach": [
            "what a graph is",
            "what vertices and edges are",
            "basic graph terminology",
            "what a weighted graph is",
        ],
    },
    {
        "id": "shortest_path",
        "match_any": [
            "shortest path",
            "dijkstra",
            "dijkstra's algorithm",
            "bellman ford",
            "bellman-ford",
        ],
        "assumed_prerequisites": [
            "graph",
            "vertex",
            "edge",
            "path",
            "weighted graph",
            "directed graph",
            "undirected graph",
        ],
        "do_not_reteach": [
            "what a graph is",
            "what vertices and edges are",
            "basic graph terminology",
            "what a weighted graph is",
        ],
    },
    {
        "id": "heap_operations",
        "match_any": [
            "heap insertion",
            "heap deletion",
            "heap push",
            "heap pop",
            "heapify",
            "min heap",
            "max heap",
            "priority queue",
        ],
        "assumed_prerequisites": [
            "heap",
            "binary tree",
            "complete binary tree",
            "parent node",
            "child node",
            "heap property",
            "array representation of a heap",
        ],
        "do_not_reteach": [
            "what a binary tree is",
            "what parent and child nodes are",
            "basic heap structure",
        ],
    },
    {
        "id": "linked_list_operations",
        "match_any": [
            "linked list insertion",
            "linked list deletion",
            "linked list traversal",
            "reverse linked list",
            "singly linked list",
            "doubly linked list",
        ],
        "assumed_prerequisites": [
            "linked list",
            "node",
            "head pointer",
            "next pointer",
            "null pointer",
        ],
        "do_not_reteach": [
            "what a linked list is",
            "what a node is",
            "what a pointer/reference is",
        ],
    },
]


def match_assumption_rules(text: str) -> list[AssumptionRule]:
    normalized_text = normalize_assumption_phrase(text)
    if not normalized_text:
        return []

    matches: list[AssumptionRule] = []
    for rule in ASSUMPTION_RULES:
        phrases = [
            normalize_assumption_phrase(phrase)
            for phrase in rule.get("match_any", [])
            if str(phrase).strip()
        ]
        if any(phrase and phrase in normalized_text for phrase in phrases):
            matches.append(rule)

    return matches
