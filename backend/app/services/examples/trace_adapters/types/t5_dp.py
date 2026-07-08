"""T5 — Dynamic-programming table fill. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.dp import (CoinChangeAdapter, EditDistanceAdapter, HouseRobberAdapter,
                           LongestIncreasingSubsequenceAdapter, MaxSubarrayAdapter, RodCuttingAdapter)

LONGEST_INCREASING_SUBSEQUENCE = declare(LongestIncreasingSubsequenceAdapter, "longest_increasing_subsequence", "T5")
COIN_CHANGE = declare(CoinChangeAdapter, "coin_change", "T5")
HOUSE_ROBBER = declare(HouseRobberAdapter, "house_robber", "T5")
MAX_SUBARRAY = declare(MaxSubarrayAdapter, "max_subarray", "T5")
ROD_CUTTING = declare(RodCuttingAdapter, "rod_cutting", "T5")
EDIT_DISTANCE = declare(EditDistanceAdapter, "edit_distance", "T5")

DECLARATIONS = [LONGEST_INCREASING_SUBSEQUENCE, COIN_CHANGE, HOUSE_ROBBER, MAX_SUBARRAY, ROD_CUTTING,
                EDIT_DISTANCE]
