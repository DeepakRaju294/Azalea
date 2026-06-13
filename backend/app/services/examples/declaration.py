"""Declaration + fixture selection (EXAMPLE_SYSTEM_SPEC.md §5.1, §5.2).

Deterministic, no LLM. `declare_example` resolves a topic to
`(application, resolved_example_type, pattern)` via the title patterns + the
code-vs-concept gate; `pick_fixture` chooses the concrete fixture for that lens +
card role.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.core.course_blueprints import normalize_topic_type_key
from app.core.example_applications import APPLICATION_PROFILES, match_application
from app.core.example_fixtures import CanonicalFixture, fixtures_for

# card role -> selection policy (spec §5.2). The policy filters a fixture's tags.
FIXTURE_SELECTION_POLICY: dict[str, str] = {
    "worked_example": "medium_nontrivial",
    "edge_case": "edge_case",
    "practice": "isomorphic_variant",
    "comparison": "contrast_pair",
}


@dataclass(frozen=True)
class DeclaredExample:
    application: str
    resolved_example_type: str   # AFTER the code-vs-concept gate
    pattern: str                 # the HOW for the resolved lens
    card_role: str
    variant: Optional[str] = None


def _blueprint_allows(topic_type: str, blueprint_key: str) -> bool:
    """The topic type's blueprint must own the slot — a study-path intro has no
    worked_example, so no example may be declared for it (spec §6)."""
    from app.core.course_blueprints import get_topic_blueprint

    blueprint = get_topic_blueprint(topic_type)
    allowed: set[str] = set()
    for key in ("default_card_sequence", "optional_cards", "continuation_card_sequence", "continuation_optional_cards"):
        allowed |= set(blueprint.get(key) or [])
    return blueprint_key in allowed


def declare_example(topic: dict[str, Any], card_role: str = "worked_example") -> Optional[DeclaredExample]:
    """Topic → DeclaredExample, or None (→ legacy). See spec §5.1."""
    application = match_application(str(topic.get("title") or ""))
    if application is None:
        return None
    profile = APPLICATION_PROFILES.get(application)
    if profile is None:
        return None  # recognised title with no profile yet → inert, fall through to legacy

    topic_type = normalize_topic_type_key(topic.get("topic_type"))
    if not _blueprint_allows(topic_type, "worked_example"):
        return None  # e.g. study_path_introduction: background + roadmap only
    variant = _detect_variant(application, str(topic.get("title") or ""))
    if topic_type == "coding_implementation" and profile.code_example_type is not None:
        return DeclaredExample(application, profile.code_example_type, profile.code_pattern or profile.pattern, card_role, variant)
    return DeclaredExample(application, profile.example_type, profile.pattern, card_role, variant)


_VARIANT_PATTERNS: dict[str, list[tuple[str, str]]] = {
    # WHICH sub-op a title names; a fixture must match it (spec §3.2 variant axis).
    "tree_traversal": [
        ("inorder", r"\bin\s*-?\s*order\b"),
        ("preorder", r"\bpre\s*-?\s*order\b"),
        ("postorder", r"\bpost\s*-?\s*order\b"),
        ("level_order", r"\blevel\s*-?\s*order\b"),
    ],
}


def _detect_variant(application: str, title: str) -> Optional[str]:
    import re

    for variant, pattern in _VARIANT_PATTERNS.get(application, []):
        if re.search(pattern, title, re.IGNORECASE):
            return variant
    return None


def pick_fixture(
    declared: DeclaredExample,
    card_role: Optional[str] = None,
    seed: Optional[object] = None,
) -> Optional[CanonicalFixture]:
    """Choose the fixture for the declared lens + card role (spec §5.2). Returns None
    if no fixture matches that lens/role yet — keeping the application inert.

    `seed` (the topic) brings in Tier-2 generated scenarios (§7.1) so similar topics
    get stable-but-varied examples; without it (and tests), only hand-verified
    fixtures are used."""
    import hashlib

    role = card_role or declared.card_role
    policy = FIXTURE_SELECTION_POLICY.get(role, "medium_nontrivial")

    pool = list(fixtures_for(declared.application))
    if seed is not None:
        from app.services.examples.generators import generated_fixtures
        pool += generated_fixtures(declared.application, seed)

    candidates = [
        fx for fx in pool
        if fx.example_type == declared.resolved_example_type and fx.pattern == declared.pattern
    ]
    # The variant axis is a hard filter: a Postorder topic must NEVER get the
    # inorder fixture — no variant match means legacy, not wrong content.
    if declared.variant is not None:
        candidates = [fx for fx in candidates if fx.variant == declared.variant]
    if not candidates:
        return None

    # Prefer fixtures tagged for this role's policy; else fall back to the full set.
    tagged = [fx for fx in candidates if policy in fx.tags]
    final = tagged or candidates
    if seed is None or len(final) == 1:
        return final[0]
    # Stable, varied selection across topics (cross-run-stable hash).
    idx = int(hashlib.md5(f"{seed}:{role}".encode()).hexdigest(), 16) % len(final)
    return final[idx]
