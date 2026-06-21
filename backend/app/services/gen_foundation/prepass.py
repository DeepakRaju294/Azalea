"""Deterministic pre-pass configuration (spec §2).

The backend computes all stable structural decisions before the single first-pass
call and passes them in; the model fills content within these constraints and does
NOT invent structure. Pure — no LLM, derived only from the topic record.
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Any, Optional

from .trace import PROJECTION_CAPS, TraceMode, caps_for_category

# Minimum element count for an array/list-based example input. A size-4 array hides the algorithm's
# behaviour (and the model gravitates to the same tiny canonical arrays); >=6 shows real structure
# and varies between generations. Tunable via env.
_MIN_ARRAY_SIZE = max(1, int(os.getenv("AZALEA_MIN_EXAMPLE_ARRAY_SIZE", "6")))

# topic families whose worked example operates on an array — we generate the input for these so the
# size is guaranteed and the values vary per study path (addresses the "same numbers" repetition).
_ARRAY_SORT_FAMILIES = {"array_sort", "recursive_divide_and_conquer", "sorting"}
_BINARY_SEARCH_FAMILIES = {"binary_search"}

# topic_type -> example category that drives the projection caps (§5.2).
_CATEGORY_BY_TOPIC_TYPE: dict[str, str] = {
    "coding_implementation": "coding_implementation",
    "algorithm_walkthrough": "algorithm_walkthrough",
    "data_structure_operation": "algorithm_walkthrough",
    "concept": "simple_concept",
    "definition": "simple_concept",
    "formula": "simple_concept",
    "proof": "simple_concept",
    "comparison": "simple_concept",
}

# topic families that warrant the larger recursive/DP band.
_COMPLEX_FAMILIES = {
    "recursive_divide_and_conquer", "recursion", "dynamic_programming", "dp", "backtracking",
}

# state_schema by topic family (the closed delta vocabulary, §7.1).
_SCHEMA_BY_FAMILY: dict[str, str] = {
    "recursive_divide_and_conquer": "merge_state_v1",
    "array_sort": "merge_state_v1",
    "binary_search": "binary_search_v1",
    "graph_traversal": "graph_traversal_v1",
}


@dataclass(frozen=True)
class PrepassConfig:
    topic_type: str
    topic_family: str
    example_mode: str               # "coding_implementation" | "math" | "concept" | ...
    example_category: str           # key into PROJECTION_CAPS
    required_cases: list[str]
    trace_mode: TraceMode
    state_schema: Optional[str]
    grouping_policy: str
    minimum_example_cards: int
    target_example_cards: int
    maximum_example_cards: int
    needs_worked_example: bool
    coding_implementation: bool
    code_language: Optional[str]
    min_example_array_size: int = _MIN_ARRAY_SIZE
    example_input: Optional[dict[str, Any]] = None  # backend-chosen input (array families), or None

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic_type": self.topic_type,
            "topic_family": self.topic_family,
            "example_mode": self.example_mode,
            "example_category": self.example_category,
            "required_cases": list(self.required_cases),
            "trace_mode": self.trace_mode,
            "state_schema": self.state_schema,
            "grouping_policy": self.grouping_policy,
            "minimum_example_cards": self.minimum_example_cards,
            "target_example_cards": self.target_example_cards,
            "maximum_example_cards": self.maximum_example_cards,
            "needs_worked_example": self.needs_worked_example,
            "coding_implementation": self.coding_implementation,
            "code_language": self.code_language,
            "min_example_array_size": self.min_example_array_size,
            "example_input": self.example_input,
        }


_GROUPING_POLICY = (
    "one card per coherent teaching transition; group all of a transition's actions into work; "
    "split only if work would exceed ~6 actions (§5.1)"
)


def _category_for(topic_type: str, topic_family: str) -> str:
    if topic_family in _COMPLEX_FAMILIES:
        return "complex_recursive_dp"
    return _CATEGORY_BY_TOPIC_TYPE.get(topic_type, "simple_concept")


def _trace_mode_for(*, coding: bool, code_preexists: bool) -> TraceMode:
    """Trace mode by INPUT AVAILABILITY (§6.1).

    Non-coding → ``model_only`` (no executor). Coding with code supplied before the
    call → ``preexisting_trace``. Coding with code generated in-pass (the default) →
    ``post_generation_trace``. ``canonical`` is opt-in elsewhere, never auto-derived.
    """
    if not coding:
        return "model_only"
    return "preexisting_trace" if code_preexists else "post_generation_trace"


# Keyword detection so a varied >=min input is chosen even when the topic_family string doesn't match
# a known key (the family classifier is inconsistent: 'divide_and_conquer', 'sorting_algorithm', '',
# etc.). Title is the strongest signal for "this example runs on an array".
_SORT_KEYWORDS = ("sort", "partition", "merge", "quick", "bubble", "insertion", "selection", "heap")
_SEARCH_KEYWORDS = ("binary search", "binary_search")
_ARRAY_KEYWORDS = ("array", "list", "subarray")


def generate_example_input(
    topic_family: str, title: str = "", min_size: int = _MIN_ARRAY_SIZE
) -> Optional[dict[str, Any]]:
    """Backend-chosen, varied input for array-based topics — guarantees size >= ``min_size`` and
    differs per generation (so two study paths of the same concept don't reuse the same array).
    Detection is by family OR title keywords (the family string is unreliable). Returns ``None`` for
    non-array topics (the model then chooses its own input)."""
    fam = (topic_family or "").lower()
    text = f"{fam} {(title or '').lower()}"
    size = random.randint(min_size, min_size + 2)

    is_search = fam in _BINARY_SEARCH_FAMILIES or any(k in text for k in _SEARCH_KEYWORDS)
    is_sort = (
        fam in _ARRAY_SORT_FAMILIES
        or "sort" in fam or "divide_and_conquer" in fam
        or any(k in text for k in _SORT_KEYWORDS)
    )
    is_array = is_sort or any(k in text for k in _ARRAY_KEYWORDS)

    if is_search:
        nums = sorted(random.sample(range(1, 99), size))
        return {"nums": nums, "target": random.choice(nums)}  # target present -> a found case
    if is_array:
        arr = [random.randint(1, 99) for _ in range(size)]
        if size >= 4:  # a duplicate makes the example more instructive (stable/partition behaviour)
            arr[random.randrange(size)] = arr[random.randrange(size)]
        return {"array": arr}
    return None


def build_prepass_config(topic: dict[str, Any]) -> PrepassConfig:
    """Derive the immutable pre-pass config from a topic record (pure)."""
    topic_type = str(topic.get("topic_type") or topic.get("type") or "concept")
    topic_family = str(topic.get("topic_family") or topic.get("family") or "")
    coding = topic_type == "coding_implementation" or bool(topic.get("coding_implementation"))
    code_preexists = bool(topic.get("code"))  # code supplied before generation (§6.1)

    category = _category_for(topic_type, topic_family)
    low, high = caps_for_category(category)
    target = (low + high) // 2

    required = [str(c) for c in (topic.get("required_cases") or [])]

    return PrepassConfig(
        topic_type=topic_type,
        topic_family=topic_family,
        example_mode="coding_implementation" if coding else "math",
        example_category=category,
        required_cases=required,
        trace_mode=_trace_mode_for(coding=coding, code_preexists=code_preexists),
        state_schema=_SCHEMA_BY_FAMILY.get(topic_family),
        grouping_policy=_GROUPING_POLICY,
        minimum_example_cards=low,
        target_example_cards=target,
        maximum_example_cards=high,
        needs_worked_example=bool(topic.get("needs_worked_example", True)),
        coding_implementation=coding,
        code_language=topic.get("code_language") if coding else None,
        min_example_array_size=_MIN_ARRAY_SIZE,
        example_input=generate_example_input(
            topic_family, str(topic.get("title") or topic.get("name") or ""), _MIN_ARRAY_SIZE
        ),
    )
