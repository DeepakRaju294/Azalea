"""Algorithm trace adapters (WORKED_EXAMPLE_REASONING_SPEC §15) — the bounded per-algorithm surface.

Adapters are organized by FAMILY (WORKED_EXAMPLE_ACCURACY_SPEC §15.3), one module per family in `families/`;
each family owns shared machinery (generators, normalizers, visuals) and hosts many algorithms as compact
classes. New algorithms are added to their family module, not as new files. Routing is in trace_pipeline.
"""
from .families.algebra import QuadraticEquationAdapter
from .families.formula import ArithmeticEvalAdapter
from .families.graph import (BFSAdapter, DFSIterativeAdapter, DijkstraAdapter, KruskalAdapter, PrimAdapter)
from .families.physics import KinematicsAdapter
from .families.sequence import BinarySearchAdapter, MergeSortAdapter
from .families.trees import InorderTraversalAdapter

# Explicit slug -> adapter registry (no fuzzy keyword matching; routing is in trace_pipeline, §17).
ADAPTERS = {a.slug: a for a in (
    BinarySearchAdapter(), BFSAdapter(), DFSIterativeAdapter(), KruskalAdapter(), MergeSortAdapter(),
    ArithmeticEvalAdapter(), DijkstraAdapter(), PrimAdapter(),
    InorderTraversalAdapter(),         # TEMPLATE — coding concept (tree family)
    QuadraticEquationAdapter(),        # TEMPLATE — math concept (algebra family, no code)
    KinematicsAdapter(),               # TEMPLATE — science concept (physics family, no code)
)}

__all__ = ["BinarySearchAdapter", "BFSAdapter", "DFSIterativeAdapter", "KruskalAdapter",
           "MergeSortAdapter", "ArithmeticEvalAdapter", "DijkstraAdapter", "PrimAdapter",
           "InorderTraversalAdapter", "QuadraticEquationAdapter", "KinematicsAdapter", "ADAPTERS"]
