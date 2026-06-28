"""Algorithm trace adapters (WORKED_EXAMPLE_REASONING_SPEC §15) — the bounded per-algorithm surface.

Adapters are organized by FAMILY (WORKED_EXAMPLE_ACCURACY_SPEC §15.3), one module per family in `families/`;
each family owns shared machinery (generators, normalizers, visuals) and hosts many algorithms as compact
classes. New algorithms are added to their family module, not as new files. Routing is in trace_pipeline.
"""
from .families.formula import ArithmeticEvalAdapter
from .families.graph import (BFSAdapter, DFSIterativeAdapter, DijkstraAdapter, KruskalAdapter, PrimAdapter)
from .families.sequence import BinarySearchAdapter, MergeSortAdapter

# Explicit slug -> adapter registry (no fuzzy keyword matching; routing is in trace_pipeline, §17).
ADAPTERS = {a.slug: a for a in (
    BinarySearchAdapter(), BFSAdapter(), DFSIterativeAdapter(), KruskalAdapter(), MergeSortAdapter(),
    ArithmeticEvalAdapter(), DijkstraAdapter(), PrimAdapter(),
)}

__all__ = ["BinarySearchAdapter", "BFSAdapter", "DFSIterativeAdapter", "KruskalAdapter",
           "MergeSortAdapter", "ArithmeticEvalAdapter", "DijkstraAdapter", "PrimAdapter", "ADAPTERS"]
