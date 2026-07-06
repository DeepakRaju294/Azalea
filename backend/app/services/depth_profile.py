"""Phase-1A structural depth (ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC §4.1/§4.2).

`depth_level` (intuition · working · deep) controls the STRUCTURAL knobs of a path — optional-card inclusion,
edge-case inclusion, practice-prompt count, verified-example instance count — independent of the Phase-2
rhetorical/rendering depth.

This module owns two things:
1. `DEPTH_PROFILE_V1` — the target knob values per depth level, and per-topic-type Phase-1A *capabilities*
   (which deep-only expansions a topic type can actually honor).
2. `compute_effective_depth(...)` — the honest resolver: `deep` is only material when ≥1 applicable topic
   supports a deep-only expansion. A path that can't materially differ from `working` is disclosed as
   `working_limited` rather than silently claiming `deep` (§4.2). PURE — no DB, no generation call.

Not yet wired: actually EMITTING the extra cards/practice/instances at generation time (that needs the
blueprint/card-generator audit + per-type count decisions). Until then this computes + discloses effective depth
onto the generation snapshot, which is what the §7 "deep never silently equals working" contract requires.
"""
from __future__ import annotations

from typing import Any, Iterable

DEPTH_PROFILE_VERSION = "v1"
DEPTH_LEVELS = ("intuition", "working", "deep")
DEFAULT_DEPTH = "working"

# Target structural knobs per depth level (the "how much" the plan aims for when capabilities allow).
DEPTH_PROFILE_V1: dict[str, dict[str, Any]] = {
    "intuition": {"optional_cards": False, "edge_cases": False, "practice_prompts": 1, "adapter_instances": 1},
    "working":   {"optional_cards": True,  "edge_cases": False, "practice_prompts": 2, "adapter_instances": 1},
    "deep":      {"optional_cards": True,  "edge_cases": True,  "practice_prompts": 3, "adapter_instances": 2},
}

# Per-topic-type Phase-1A capabilities: which deep-only expansions the type can honor. A type supports a
# "deep expansion" if it can add an edge case, an optional card, or a 2nd verified instance. Types that teach a
# single qualitative idea (intro/terminology/plain concept) cannot, so a path made only of them can't be `deep`.
_TYPE_CAPABILITIES: dict[str, dict[str, Any]] = {
    "algorithm_walkthrough":       {"edge_cases": True,  "optional_cards": True,  "max_adapter_instances": 2},
    "data_structure_operation":    {"edge_cases": True,  "optional_cards": True,  "max_adapter_instances": 2},
    "coding_implementation":       {"edge_cases": True,  "optional_cards": True,  "max_adapter_instances": 2},
    "math_formula_method":         {"edge_cases": True,  "optional_cards": True,  "max_adapter_instances": 2},
    "proof_reasoning":             {"edge_cases": True,  "optional_cards": True,  "max_adapter_instances": 1},
    "problem_solving_application": {"edge_cases": True,  "optional_cards": True,  "max_adapter_instances": 2},
    "science_mechanism":           {"edge_cases": False, "optional_cards": True,  "max_adapter_instances": 1},
    "process_walkthrough":         {"edge_cases": False, "optional_cards": True,  "max_adapter_instances": 1},
    "compare_distinguish":         {"edge_cases": False, "optional_cards": True,  "max_adapter_instances": 1},
    "concept_intuition":           {"edge_cases": False, "optional_cards": False, "max_adapter_instances": 1},
    "terminology_components":      {"edge_cases": False, "optional_cards": False, "max_adapter_instances": 1},
    "study_path_introduction":     {"edge_cases": False, "optional_cards": False, "max_adapter_instances": 1},
}
_DEFAULT_CAPABILITY = {"edge_cases": False, "optional_cards": False, "max_adapter_instances": 1}


def capabilities_for(topic_type: str | None) -> dict[str, Any]:
    """Phase-1A capabilities for a topic type (conservative default for anything unlisted)."""
    return _TYPE_CAPABILITIES.get(str(topic_type or "").strip().lower(), _DEFAULT_CAPABILITY)


def _supports_deep_expansion(cap: dict[str, Any]) -> bool:
    return bool(cap.get("edge_cases") or cap.get("optional_cards") or cap.get("max_adapter_instances", 1) >= 2)


def compute_effective_depth(selected_depth: str | None, topic_types: Iterable[str | None]) -> dict[str, Any]:
    """Resolve the honest path-level depth (§4.2).

    - `intuition`/`working` are always `honored` (they don't over-claim).
    - `deep` is `honored` only when ≥1 applicable topic supports a deep-only expansion; if NONE do, it is
      downgraded to `effective_depth='working_limited'` with reason `no_material_expansion_available`. When some
      but not all topics support it, depth is still honored path-level and `deep_where_supported` is set (disclose
      'Deep mode applied where supported').
    """
    selected = selected_depth if selected_depth in DEPTH_LEVELS else DEFAULT_DEPTH
    types = [str(t or "").strip().lower() for t in topic_types if str(t or "").strip()]

    if selected != "deep":
        return {
            "selected_depth": selected,
            "effective_depth": selected,
            "effective_depth_reason": "honored",
            "deep_where_supported": False,
            "expandable_topic_count": 0,
            "profile_version": DEPTH_PROFILE_VERSION,
        }

    expandable = [t for t in types if _supports_deep_expansion(capabilities_for(t))]
    if not expandable:
        return {
            "selected_depth": "deep",
            "effective_depth": "working_limited",
            "effective_depth_reason": "no_material_expansion_available",
            "deep_where_supported": False,
            "expandable_topic_count": 0,
            "profile_version": DEPTH_PROFILE_VERSION,
        }
    return {
        "selected_depth": "deep",
        "effective_depth": "deep",
        "effective_depth_reason": "honored",
        "deep_where_supported": len(expandable) < len(types),   # partial ⇒ disclose "where supported"
        "expandable_topic_count": len(expandable),
        "profile_version": DEPTH_PROFILE_VERSION,
    }
