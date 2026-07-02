"""Algorithm trace adapters (WORKED_EXAMPLE_REASONING_SPEC §15) — the bounded per-algorithm surface.

Adapters are organized by FAMILY (WORKED_EXAMPLE_ACCURACY_SPEC §15.3), one module per family in `families/`;
each family owns shared machinery (generators, normalizers, visuals) and hosts many algorithms as compact
classes. New algorithms are added to their family module, not as new files. Routing is in trace_pipeline.
"""
from .families.algebra import QuadraticEquationAdapter
from .families.formula import ArithmeticEvalAdapter
from .families.graph import (BFSAdapter, DFSIterativeAdapter, DijkstraAdapter, KruskalAdapter, PrimAdapter)
from .families.physics import KinematicsAdapter
from .families.sequence import (BinarySearchAdapter, BubbleSortAdapter, InsertionSortAdapter,
                                MergeSortAdapter, SelectionSortAdapter)
from .families.trees import (BSTSearchAdapter, InorderTraversalAdapter, LevelOrderTraversalAdapter,
                             PostorderTraversalAdapter, PreorderTraversalAdapter)

# Explicit slug -> adapter registry (no fuzzy keyword matching; routing is in trace_pipeline, §17).
ADAPTERS = {a.slug: a for a in (
    BinarySearchAdapter(), BFSAdapter(), DFSIterativeAdapter(), KruskalAdapter(), MergeSortAdapter(),
    InsertionSortAdapter(), SelectionSortAdapter(), BubbleSortAdapter(),  # T8a pilots — grow a sorted region a pass at a time
    ArithmeticEvalAdapter(), DijkstraAdapter(), PrimAdapter(),
    InorderTraversalAdapter(),         # TEMPLATE — coding concept (tree family)
    PreorderTraversalAdapter(), PostorderTraversalAdapter(), LevelOrderTraversalAdapter(),  # verified traversal siblings
    QuadraticEquationAdapter(),        # TEMPLATE — math concept (algebra family, no code)
    KinematicsAdapter(),               # TEMPLATE — science concept (physics family, no code)
    BSTSearchAdapter(),                # T4 GATE — second search state model (tree node, not array bounds)
)}

__all__ = ["BinarySearchAdapter", "BFSAdapter", "DFSIterativeAdapter", "KruskalAdapter",
           "MergeSortAdapter", "InsertionSortAdapter", "SelectionSortAdapter", "BubbleSortAdapter", "ArithmeticEvalAdapter", "DijkstraAdapter", "PrimAdapter",
           "InorderTraversalAdapter", "PreorderTraversalAdapter", "PostorderTraversalAdapter",
           "LevelOrderTraversalAdapter", "QuadraticEquationAdapter", "KinematicsAdapter",
           "BSTSearchAdapter", "ADAPTERS"]
