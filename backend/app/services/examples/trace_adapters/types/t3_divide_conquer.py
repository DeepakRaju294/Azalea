"""T3 — Divide and conquer. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.sequence import MergeSortAdapter, QuickSortAdapter

MERGE_SORT = declare(MergeSortAdapter, "merge_sort", "T3")
QUICK_SORT = declare(QuickSortAdapter, "quick_sort", "T3")

DECLARATIONS = [MERGE_SORT, QUICK_SORT]
