"""Algorithm trace adapters — the bounded per-algorithm surface (WORKED_EXAMPLE_REASONING_SPEC.md §15)."""
from .binary_search import BinarySearchAdapter

# Phase 1: explicit slug -> adapter routing (no fuzzy keyword matching, §17).
ADAPTERS = {BinarySearchAdapter.slug: BinarySearchAdapter()}

__all__ = ["BinarySearchAdapter", "ADAPTERS"]
