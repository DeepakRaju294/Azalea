"""Deterministic per-topic BST value sets.

Shared by two places so they always agree:
  - the lesson prompt (`_tree_value_directive`), which tells the model to use
    these exact numbers, and
  - the visual bridge, which falls back to them when the model emits a
    malformed tree (e.g. a node labelled "WITH", or too few nodes) that its
    numeric BST rebuild can't process.

Because both seed from the same topic string, the fallback tree the bridge
renders matches the values the prompt asked the model to write in the prose.
"""

from __future__ import annotations

import hashlib
import random


def generate_bst_value_set(seed_source: str) -> tuple[list[int], int]:
    """Return (sorted distinct integer values, root) for a topic.

    Stable for a given `seed_source` (so regenerations match), distinct across
    topics. The root is the median, so a balanced BST over the set is rooted
    exactly where the prose says.
    """
    rng = random.Random(
        int(hashlib.sha256(seed_source.encode("utf-8")).hexdigest()[:12], 16)
    )
    count = rng.choice((7, 8, 9))
    values = sorted(rng.sample(range(11, 96), count))
    root = values[count // 2]
    return values, root
