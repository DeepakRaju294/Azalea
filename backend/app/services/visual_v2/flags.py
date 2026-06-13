"""Per-mode feature flag (VISUAL_SYSTEM_SPEC §8, §8.1).

`AZALEA_VISUAL_V2_MODES` is a comma list of enabled keys. Forgiving matching — any
of these enable a mode: the literal `all`; the mode (`graph_network`,
`binary_search_range`, `code_execution`); the `mode:algorithm` pair; or just the
algorithm name (`bfs`, `binary_search`, ...). So
`AZALEA_VISUAL_V2_MODES=all` turns everything on, and `binary_search` works the
same as `binary_search_range`.
"""
from __future__ import annotations

import os


def enabled_keys() -> set[str]:
    raw = os.getenv("AZALEA_VISUAL_V2_MODES", "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def is_v2_enabled(mode: str, algorithm: str | None) -> bool:
    keys = enabled_keys()
    if not keys:
        return False
    if "all" in keys:
        return True
    mode = (mode or "").lower()
    algo = (algorithm or "").lower()
    if mode in keys:
        return True
    if algo and (algo in keys or f"{mode}:{algo}" in keys):
        return True
    return False
