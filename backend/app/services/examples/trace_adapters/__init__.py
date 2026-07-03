"""Algorithm trace adapters (WORKED_EXAMPLE_REASONING_SPEC §15) — the bounded per-algorithm surface.

Adapters are organized by FAMILY (WORKED_EXAMPLE_ACCURACY_SPEC §15.3), one module per family in `families/`;
each family owns shared machinery (generators, normalizers, visuals) and hosts many algorithms as compact
classes. New algorithms are added to their family module, not as new files. Routing is in trace_pipeline.
"""
from .families.algebra import QuadraticEquationAdapter
from .families.backtracking import NQueensAdapter
from .families.dp import LongestIncreasingSubsequenceAdapter
from .families.execution import EuclidGCDAdapter
from .families.formula import ArithmeticEvalAdapter
from .families.graph import (BellmanFordAdapter, BFSAdapter, DFSIterativeAdapter, DijkstraAdapter,
                             KruskalAdapter, PrimAdapter)
from .families.physics import KinematicsAdapter
from .families.proof import InductionProofAdapter
from .families.structures import UnionFindAdapter
from .families.sequence import (BinarySearchAdapter, BubbleSortAdapter, HeapSortAdapter,
                                InsertionSortAdapter, MergeSortAdapter, QuickSortAdapter,
                                SelectionSortAdapter)
from .families.trees import (BSTSearchAdapter, InorderTraversalAdapter, LevelOrderTraversalAdapter,
                             PostorderTraversalAdapter, PreorderTraversalAdapter)

# Explicit slug -> adapter registry (no fuzzy keyword matching; routing is in trace_pipeline, §17).
ADAPTERS = {a.slug: a for a in (
    BinarySearchAdapter(), BFSAdapter(), DFSIterativeAdapter(), KruskalAdapter(), MergeSortAdapter(),
    InsertionSortAdapter(), SelectionSortAdapter(), BubbleSortAdapter(), HeapSortAdapter(),  # T8a pilots — grow a sorted region a pass at a time
    QuickSortAdapter(),                # T3 — 2nd divide-and-conquer pilot (partition-in-place) after merge sort
    ArithmeticEvalAdapter(), DijkstraAdapter(), PrimAdapter(),
    BellmanFordAdapter(),              # T9a PILOT — repeated relaxation / iterative refinement (directed graph)
    UnionFindAdapter(),                # T10 PILOT — stateful invariant maintenance (mutable disjoint-set forest)
    EuclidGCDAdapter(),                # T12 PILOT — program execution / memory trace (loop + evolving variables)
    InductionProofAdapter(),           # T8b PILOT — formal derivation (proof by induction; numeric-oracle refereed)
    InorderTraversalAdapter(),         # TEMPLATE — coding concept (tree family)
    PreorderTraversalAdapter(), PostorderTraversalAdapter(), LevelOrderTraversalAdapter(),  # verified traversal siblings
    QuadraticEquationAdapter(),        # TEMPLATE — math concept (algebra family, no code)
    KinematicsAdapter(),               # TEMPLATE — science concept (physics family, no code)
    BSTSearchAdapter(),                # T4 GATE — second search state model (tree node, not array bounds)
    LongestIncreasingSubsequenceAdapter(),   # T5 PILOT — first dynamic-programming adapter (1-D table fill)
    NQueensAdapter(),                  # T11 PILOT — backtracking (place / conflict / BACKTRACK; non-monotonic search)
)}

__all__ = ["BinarySearchAdapter", "BFSAdapter", "DFSIterativeAdapter", "KruskalAdapter",
           "MergeSortAdapter", "QuickSortAdapter", "InsertionSortAdapter", "SelectionSortAdapter", "BubbleSortAdapter", "HeapSortAdapter", "ArithmeticEvalAdapter", "DijkstraAdapter", "PrimAdapter",
           "InorderTraversalAdapter", "PreorderTraversalAdapter", "PostorderTraversalAdapter",
           "LevelOrderTraversalAdapter", "QuadraticEquationAdapter", "KinematicsAdapter",
           "BSTSearchAdapter", "LongestIncreasingSubsequenceAdapter", "NQueensAdapter", "BellmanFordAdapter", "UnionFindAdapter", "EuclidGCDAdapter", "InductionProofAdapter", "ADAPTERS"]
