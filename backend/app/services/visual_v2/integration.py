"""Integration seam (VISUAL_SYSTEM_SPEC §8.1 step 9).

`maybe_build_v2_visual(topic)` is the single, flag-gated entry point a caller in
the lesson build uses: it returns a V2 result when the topic's (mode, algorithm)
is enabled, else None (caller keeps the legacy path). The flag is default-off, so
importing/calling this is inert until AZALEA_VISUAL_V2_MODES is set.

Pilot scope: graph BFS/DFS walkthroughs. Tree/array/code detection is added as
those modes come online.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from .build import build_v2_visual
from .flags import is_v2_enabled
from .llm import default_example_generator, default_prose_generator


def detect_mode_algorithm(topic: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Pilot-scoped declaration: map a topic to (mode, algorithm). Graph BFS/DFS
    walkthroughs only for now; coding/tree topics fall through (None, None)."""
    topic_type = str(topic.get("topic_type") or topic.get("course_type") or "").lower()
    if "coding" in topic_type:
        return (None, None)  # code_execution mode not built yet
    text = f"{topic.get('title', '')} {topic_type}".lower()
    if "breadth-first" in text or re.search(r"\bbfs\b", text):
        return ("graph_network", "bfs")
    if "depth-first" in text or re.search(r"\bdfs\b", text):
        return ("graph_network", "dfs")
    return (None, None)


def maybe_build_v2_visual(
    topic: dict[str, Any],
    *,
    generate_example: Optional[Callable[..., Any]] = None,
    generate_prose: Optional[Callable[..., Any]] = None,
) -> Optional[dict[str, Any]]:
    """Return a V2 build result if this topic is V2-enabled, else None."""
    mode, algorithm = detect_mode_algorithm(topic)
    if not mode or not algorithm:
        return None
    if not is_v2_enabled(mode, algorithm):
        return None
    return build_v2_visual(
        topic=topic,
        mode=mode,
        algorithm=algorithm,
        generate_example=generate_example or default_example_generator,
        generate_prose=generate_prose if generate_prose is not None else default_prose_generator,
    )
