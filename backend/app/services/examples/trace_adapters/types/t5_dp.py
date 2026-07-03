"""T5 — Dynamic-programming table fill. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.dp import CoinChangeAdapter, LongestIncreasingSubsequenceAdapter

LONGEST_INCREASING_SUBSEQUENCE = declare(LongestIncreasingSubsequenceAdapter, "longest_increasing_subsequence", "T5")
COIN_CHANGE = declare(CoinChangeAdapter, "coin_change", "T5")

DECLARATIONS = [LONGEST_INCREASING_SUBSEQUENCE, COIN_CHANGE]
